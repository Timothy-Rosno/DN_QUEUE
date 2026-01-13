"""
Middleware for checking and sending pending checkout reminders.

This middleware runs on every request to check if any checkout reminders are due.
This replaces the Celery scheduled tasks approach.
"""
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from zoneinfo import ZoneInfo
from .models import QueueEntry
from . import notifications
from .render_usage import increment_request_count


class CheckReminderMiddleware:
    """
    Middleware that checks for pending checkout reminders on every request.

    This runs after authentication middleware so we can access request.user.
    It checks for any QueueEntry where:
    - reminder_due_at is in the past (initial reminder trigger)
    - OR it's been 2+ hours since last_reminder_sent_at (repeat reminders)
    - status is still 'running' (meaning user hasn't checked out yet)
    - current time is NOT between 12 AM - 6 AM (no reminders during night hours)

    Reminders are sent every 12 hours until the user checks out.
    Using database-level locking to prevent duplicate notifications.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip middleware for health check endpoint to avoid DB queries during cold starts
        if request.path == '/schedule/health/':
            return self.get_response(request)

        # Check for pending reminders BEFORE processing the request
        # OPTIMIZATION: Only check once per minute to reduce database compute usage
        # Use cache to track last check time
        from django.core.cache import cache
        last_check = cache.get('reminder_last_check')
        now_timestamp = timezone.now().timestamp()

        # Only check if more than 60 seconds since last check (or never checked)
        if last_check is None or (now_timestamp - last_check) > 60:
            self._check_pending_reminders()
            self._check_pending_checkin_reminders()
            # Update cache with current timestamp
            cache.set('reminder_last_check', now_timestamp, 120)  # Cache for 2 minutes

        # Continue processing the request
        response = self.get_response(request)

        return response

    def _check_pending_reminders(self):
        """
        Check for and send any pending checkout reminders.

        Sends reminders every 12 hours (except 12 AM - 6 AM Central Time) until user checks out.
        Uses select_for_update() to prevent race conditions where multiple
        requests might try to send the same reminder simultaneously.
        """
        now = timezone.now()

        # Check if we're in the "do not disturb" hours (12 AM - 6 AM Central Time)
        central_tz = ZoneInfo('America/Chicago')
        now_central = now.astimezone(central_tz)
        current_hour = now_central.hour
        if 0 <= current_hour < 6:
            # Skip sending reminders during night hours
            return

        try:
            # Find all running entries that need a reminder
            # Using select_for_update() with skip_locked=True to handle concurrent requests
            # Note: Must clear default ordering to avoid LEFT OUTER JOIN on nullable assigned_machine FK
            # (PostgreSQL does not allow FOR UPDATE on nullable side of outer join)
            with transaction.atomic():
                # Get all running entries that have passed their initial reminder time
                running_entries = QueueEntry.objects.select_for_update(skip_locked=True).filter(
                    reminder_due_at__lte=now,
                    status='running'  # Only send if still running (not checked out early)
                ).order_by()  # Clear Model.Meta.ordering to prevent JOIN

                for entry in running_entries:
                    try:
                        # Check if reminder is snoozed
                        if entry.reminder_snoozed_until and entry.reminder_snoozed_until > now:
                            # Still in snooze period - skip this entry
                            continue

                        # Determine if we should send a reminder
                        should_send = False

                        if entry.last_reminder_sent_at is None:
                            # Never sent a reminder - send the first one
                            should_send = True
                        else:
                            # Check if it's been at least 2 hours since last reminder
                            time_since_last = now - entry.last_reminder_sent_at
                            if time_since_last >= timedelta(hours=12):
                                should_send = True

                        if should_send:
                            # Send the notification
                            notifications.notify_checkout_reminder(entry)

                            # Update last reminder sent time
                            entry.last_reminder_sent_at = now
                            entry.save(update_fields=['last_reminder_sent_at'])

                    except Exception as e:
                        # Log error but don't break the request
                        print(f"Error sending checkout reminder for entry {entry.id}: {e}")

        except Exception as e:
            # Don't break the request if reminder checking fails
            print(f"Error checking pending reminders: {e}")

    def _check_pending_checkin_reminders(self):
        """
        Check for and send any pending check-in reminders.

        Sends reminders every 12 hours (except 12 AM - 6 AM Central Time) until user checks in.
        For entries at position #1 that haven't checked in yet.
        Uses select_for_update() to prevent race conditions.
        """
        now = timezone.now()

        # Check if we're in the "do not disturb" hours (12 AM - 6 AM Central Time)
        central_tz = ZoneInfo('America/Chicago')
        now_central = now.astimezone(central_tz)
        current_hour = now_central.hour
        if 0 <= current_hour < 6:
            # Skip sending reminders during night hours
            return

        try:
            # Find all position #1 queued entries that need a check-in reminder
            # Using select_for_update() with skip_locked=True to handle concurrent requests
            with transaction.atomic():
                # Get all queued entries at position 1 with machines that are available
                queued_entries = QueueEntry.objects.select_for_update(skip_locked=True).filter(
                    queue_position=1,
                    status='queued',
                    assigned_machine__isnull=False,
                    assigned_machine__current_status='idle',  # Machine must be available
                    assigned_machine__is_available=True  # Machine must not be in maintenance
                ).order_by()  # Clear Model.Meta.ordering to prevent JOIN

                for entry in queued_entries:
                    try:
                        # Check if check-in reminder is initialized
                        if entry.checkin_reminder_due_at is None:
                            # Not initialized yet - skip (will be initialized when they reach position 1)
                            continue

                        # Check if past the initial due time
                        if entry.checkin_reminder_due_at > now:
                            # Not due yet
                            continue

                        # Check if reminder is snoozed
                        if entry.checkin_reminder_snoozed_until and entry.checkin_reminder_snoozed_until > now:
                            # Still in snooze period - skip this entry
                            continue

                        # Determine if we should send a reminder
                        should_send = False

                        if entry.last_checkin_reminder_sent_at is None:
                            # Never sent a reminder - send the first one
                            should_send = True
                        else:
                            # Check if it's been at least 6 hours since last reminder
                            time_since_last = now - entry.last_checkin_reminder_sent_at
                            if time_since_last >= timedelta(hours=12):
                                should_send = True

                        if should_send:
                            # Send the notification
                            notifications.notify_checkin_reminder(entry)

                            # Update last reminder sent time
                            entry.last_checkin_reminder_sent_at = now
                            entry.save(update_fields=['last_checkin_reminder_sent_at'])

                    except Exception as e:
                        # Log error but don't break the request
                        print(f"Error sending check-in reminder for entry {entry.id}: {e}")

        except Exception as e:
            # Don't break the request if reminder checking fails
            print(f"Error checking pending check-in reminders: {e}")


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


class AnalyticsMiddleware:
    """
    DISABLED: Analytics middleware to save usage on free tier.
    Google Analytics is used instead - no database writes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # DISABLED: All tracking to avoid database usage
        response = self.get_response(request)
        return response


class ErrorLoggingMiddleware:
    """
    DISABLED: Error logging middleware to save usage on free tier.
    Users will submit bug reports via feedback system instead.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # DISABLED: All error logging to avoid database writes
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        # DISABLED: Exception logging to avoid database writes
        # Return None to allow Django's default exception handling
        return None


class OnlineUserTrackingMiddleware:
    """
    DISABLED: Online user tracking to save usage on free tier.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # DISABLED: All user tracking to avoid cache/database usage
        response = self.get_response(request)
        return response
