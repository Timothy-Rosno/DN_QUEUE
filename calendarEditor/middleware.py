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
    Efficient analytics tracking using Redis counters and smart sampling.

    Strategy:
    - Use Redis for real-time counters (page views, users online)
    - Sample only 10% of page views for device/browser analysis
    - Aggregate data hourly/daily via management commands
    - Minimal database writes = minimal database reads later
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Pages to track (exclude static files, admin, etc.)
        self.tracked_paths = [
            '/schedule/submit/',
            '/schedule/my-queue/',
            '/schedule/queue/',
            '/schedule/check-in-check-out/',
            '/schedule/archive/',
            '/schedule/fridges/',
            '/',
        ]

        # Sample rate: 1 in 10 page views are stored for device/browser analysis
        self.sample_rate = 10

    def __call__(self, request):
        response = self.get_response(request)

        # Only track GET requests
        if request.method == 'GET':
            # Check if path should be tracked
            if any(request.path.startswith(path) for path in self.tracked_paths):
                self._track_page_view(request)

        return response

    def _track_page_view(self, request):
        """Track page view using cache counters + occasional DB sampling"""
        try:
            from .analytics_utils import increment_counter, add_to_set, add_to_sorted_set
            import random
            from datetime import datetime

            # Ensure session exists
            if not request.session.session_key:
                request.session.create()

            session_key = request.session.session_key or ''
            user_id = request.user.id if request.user.is_authenticated else None
            page_title = self._get_page_title(request.path)
            now = datetime.now()
            today = now.date()
            current_hour = now.hour

            # === CACHE COUNTERS (super fast, no DB writes) ===
            # Increment today's page view counter
            increment_counter(f'analytics:pageviews:{today}', 1, 86400 * 2)

            # Track unique users today
            if user_id:
                add_to_set(f'analytics:users:{today}', user_id, 86400 * 2)

            # Track unique sessions today
            add_to_set(f'analytics:sessions:{today}', session_key, 86400 * 2)

            # Track page-specific counters
            increment_counter(f'analytics:page:{page_title}:{today}', 1, 86400 * 2)

            # Track hourly counters
            increment_counter(f'analytics:hour:{today}:{current_hour}', 1, 86400 * 2)

            # Track users online (last 15 minutes)
            if user_id:
                add_to_sorted_set('analytics:users_online', user_id, now.timestamp(), 900)

            # === SAMPLED DATABASE WRITES (for device/browser analysis) ===
            # Only write to DB for 10% of requests (reduces DB load by 90%)
            if random.randint(1, self.sample_rate) == 1:
                from .models import PageView
                from .views import parse_user_agent

                # Get device info
                device_info = parse_user_agent(request)

                # Extract IP address
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0].strip()
                else:
                    ip_address = request.META.get('REMOTE_ADDR', 'Unknown')

                device_info['ip_address'] = ip_address

                # Store sampled page view
                PageView.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    session_key=session_key,
                    path=request.path,
                    page_title=page_title,
                    referrer=request.META.get('HTTP_REFERER', ''),
                    device_info=device_info,
                )

        except Exception as e:
            # Don't break requests if tracking fails
            pass

    def _get_page_title(self, path):
        """Map path to readable page title"""
        title_map = {
            '/': 'Home',
            '/schedule/submit/': 'Submit Request',
            '/schedule/my-queue/': 'My Queue',
            '/schedule/queue/': 'Public Queue',
            '/schedule/check-in-check-out/': 'Check-In/Check-Out',
            '/schedule/archive/': 'Archive',
            '/schedule/fridges/': 'Fridge Specs',
        }
        return title_map.get(path, path)


class ErrorLoggingMiddleware:
    """
    Middleware to log errors (404s, 500s, exceptions) for analytics.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log 404 errors
        if response.status_code == 404:
            self._log_error(request, response, '404')
        # Log 403 errors
        elif response.status_code == 403:
            self._log_error(request, response, '403')
        # Log 400 errors
        elif response.status_code == 400:
            self._log_error(request, response, '400')
        # Log 500 errors
        elif response.status_code >= 500:
            self._log_error(request, response, '500')

        return response

    def process_exception(self, request, exception):
        """Log unhandled exceptions"""
        try:
            import traceback
            from .models import ErrorLog

            # Get session key safely
            session_key = ''
            try:
                if hasattr(request, 'session'):
                    session_key = request.session.session_key or ''
                    if not session_key and hasattr(request.session, 'create'):
                        request.session.create()
                        session_key = request.session.session_key or ''
            except Exception:
                # Skip session if it causes issues
                pass

            # Extract IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR', None)

            ErrorLog.objects.create(
                user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                session_key=session_key,
                error_type='exception',
                path=request.path,
                method=request.method,
                status_code=500,
                error_message=str(exception),
                stack_trace=traceback.format_exc(),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=ip_address,
            )
        except Exception:
            # Don't break if logging fails
            pass

        # Return None to allow Django's default exception handling
        return None

    def _log_error(self, request, response, error_type):
        """Log error to database"""
        try:
            from .models import ErrorLog

            # Get session key safely
            session_key = ''
            try:
                if hasattr(request, 'session'):
                    session_key = request.session.session_key or ''
                    if not session_key and hasattr(request.session, 'create'):
                        request.session.create()
                        session_key = request.session.session_key or ''
            except Exception:
                # Skip session if it causes issues
                pass

            # Extract IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR', None)

            ErrorLog.objects.create(
                user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                session_key=session_key,
                error_type=error_type,
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                error_message=f"{response.status_code} error on {request.path}",
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=ip_address,
            )
        except Exception:
            # Don't break if logging fails
            pass


class OnlineUserTrackingMiddleware:
    """
    Lightweight middleware to track online users in Redis cache.
    
    No database writes - only cache operations (microsecond-level fast).
    Stores user activity with 15-minute TTL that auto-expires.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)

        # Only track authenticated users
        if request.user.is_authenticated:
            try:
                from django.core.cache import cache
                from django.utils import timezone
                import json
                
                # Get client info
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                ip_address = self._get_client_ip(request)
                
                # Parse user agent for browser/OS/device
                device_info = self._parse_user_agent(user_agent, ip_address)
                
                # Build user activity data
                activity_data = {
                    'user_id': request.user.id,
                    'username': request.user.username,
                    'email': request.user.email,
                    'last_seen': timezone.now().isoformat(),
                    'ip_address': device_info.get('ip_address', 'Unknown'),
                    'browser': device_info.get('browser', 'Unknown'),
                    'os': device_info.get('os', 'Unknown'),
                    'device': device_info.get('device', 'Unknown'),
                }
                
                # Store in cache with 15-minute TTL (900 seconds)
                cache_key = f'online_user:{request.user.id}'
                cache.set(cache_key, json.dumps(activity_data), 900)
                
            except Exception as e:
                # Don't break the request if tracking fails
                # print(f"[OnlineUserTracking] Error: {e}")
                pass
        
        return response
    
    def _get_client_ip(self, request):
        """Extract client IP from request headers."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'Unknown')
        return ip
    
    def _parse_user_agent(self, user_agent_string, ip_address):
        """Parse user agent string to extract browser, OS, device info."""
        # Simple parsing without external library
        browser = 'Unknown'
        os = 'Unknown'
        device = 'Desktop'

        ua_lower = user_agent_string.lower()

        # Detect browser
        if 'chrome' in ua_lower and 'edg' not in ua_lower:
            browser = 'Chrome'
        elif 'firefox' in ua_lower:
            browser = 'Firefox'
        elif 'safari' in ua_lower and 'chrome' not in ua_lower:
            browser = 'Safari'
        elif 'edg' in ua_lower:
            browser = 'Edge'

        # Detect OS
        if 'windows' in ua_lower:
            os = 'Windows'
        elif 'mac' in ua_lower:
            os = 'macOS'
        elif 'linux' in ua_lower:
            os = 'Linux'
        elif 'android' in ua_lower:
            os = 'Android'
        elif 'iphone' in ua_lower or 'ipad' in ua_lower:
            os = 'iOS'

        # Detect device type
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            device = 'Mobile'
        elif 'ipad' in ua_lower or 'tablet' in ua_lower:
            device = 'Tablet'

        return {
            'browser': browser,
            'os': os,
            'device': device,
            'ip_address': ip_address,
        }
