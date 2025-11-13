"""
Middleware for checking and sending pending checkout reminders.

This middleware runs on every request to check if any checkout reminders are due.
This replaces the Celery scheduled tasks approach.
"""
from django.utils import timezone
from django.db import transaction
from .models import QueueEntry
from . import notifications
from .render_usage import increment_request_count


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
        # Skip middleware for health check endpoint to avoid DB queries during cold starts
        if request.path == '/schedule/health/':
            return self.get_response(request)

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
            # Note: Must clear default ordering to avoid LEFT OUTER JOIN on nullable assigned_machine FK
            # (PostgreSQL does not allow FOR UPDATE on nullable side of outer join)
            with transaction.atomic():
                pending_entries = QueueEntry.objects.select_for_update(skip_locked=True).filter(
                    reminder_due_at__lte=now,
                    reminder_sent=False,
                    status='running'  # Only send if still running (not checked out early)
                ).order_by()  # Clear Model.Meta.ordering to prevent JOIN

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


class RenderUsageMiddleware:
    """
    Middleware to track request counts for Render usage monitoring.
    Increments counter for each request to help track usage against free tier limits.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip tracking for health checks to avoid Redis connection attempts during cold starts
        if request.path != '/schedule/health/':
            increment_request_count()

        response = self.get_response(request)
        return response
