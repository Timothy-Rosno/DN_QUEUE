"""
Middleware for checking and sending pending checkout reminders.

This middleware runs on every request to check if any checkout reminders are due.
This replaces the Celery scheduled tasks approach.
"""
from django.utils import timezone
from django.db import transaction
from .models import QueueEntry
from . import notifications


class CheckReminderMiddleware:
    """
    Middleware that checks for pending checkout reminders on every request.

    This runs after authentication middleware so we can access request.user.
    It checks for any QueueEntry where:
    - reminder_due_at is in the past
    - reminder_sent is False
    - status is still 'running' (meaning user hasn't checked out yet)

    Using database-level locking to prevent duplicate notifications.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check for pending reminders BEFORE processing the request
        # This ensures reminders are sent even if the request fails
        self._check_pending_reminders()

        # Continue processing the request
        response = self.get_response(request)

        return response

    def _check_pending_reminders(self):
        """
        Check for and send any pending checkout reminders.

        Uses select_for_update() to prevent race conditions where multiple
        requests might try to send the same reminder simultaneously.
        """
        now = timezone.now()

        try:
            # Find all entries with pending reminders
            # Using select_for_update() with skip_locked=True to handle concurrent requests
            # select_related() converts nullable foreign keys from OUTER to INNER joins,
            # which is required for PostgreSQL's FOR UPDATE locking
            with transaction.atomic():
                pending_entries = QueueEntry.objects.select_related('user', 'assigned_machine').select_for_update(skip_locked=True).filter(
                    reminder_due_at__lte=now,
                    reminder_sent=False,
                    status='running'  # Only send if still running (not checked out early)
                )

                for entry in pending_entries:
                    try:
                        # Send the notification
                        notifications.notify_checkout_reminder(entry)

                        # Mark reminder as sent
                        entry.reminder_sent = True
                        entry.save(update_fields=['reminder_sent'])

                    except Exception as e:
                        # Log error but don't break the request
                        print(f"Error sending checkout reminder for entry {entry.id}: {e}")

        except Exception as e:
            # Don't break the request if reminder checking fails
            print(f"Error checking pending reminders: {e}")
