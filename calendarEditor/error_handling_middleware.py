"""
Error Handling Middleware for Calendar Editor

Catches 404, 403, and 500 errors globally and redirects users to appropriate pages
with helpful error messages. Also sends developer notifications for critical errors.
"""

from django.http import Http404
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.contrib import messages
from django.urls import resolve
from django.db import DatabaseError, IntegrityError
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import logging
import traceback

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware:
    """
    Middleware to handle 404, 403, and 500 errors gracefully.

    Redirects users to context-aware pages with helpful error messages
    instead of showing error pages.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)

            # Handle 404 responses
            if response.status_code == 404:
                return self._handle_404(request)

            # Handle 403 responses
            if response.status_code == 403:
                return self._handle_403(request)

            # Handle 500 responses
            if response.status_code == 500:
                return self._handle_500(request, None)

            return response

        except Http404:
            return self._handle_404(request)
        except PermissionDenied:
            return self._handle_403(request)

    def process_exception(self, request, exception):
        """
        Handle exceptions raised during view processing.

        This catches 500 errors and other unhandled exceptions.
        """
        # Don't handle 404 and 403 here - they're handled in __call__
        if isinstance(exception, (Http404, PermissionDenied)):
            return None

        # Log the exception for debugging
        logger.error(
            f"Unhandled exception in {request.path}: {type(exception).__name__}: {str(exception)}",
            exc_info=True,
            extra={'request': request}
        )

        # Handle the error with a redirect
        return self._handle_500(request, exception)

    def _handle_404(self, request):
        """Handle 404 errors with custom error page"""
        path = request.path

        # Render custom 404 page
        response = render(request, '404.html', {
            'request_path': path,
        }, status=404)

        return response

    def _handle_403(self, request):
        """Handle permission denied errors with custom error page"""
        path = request.path

        # Render custom 403 page
        response = render(request, '403.html', {
            'request_path': path,
        }, status=403)

        return response

    def _handle_500(self, request, exception):
        """Handle 500 errors with custom error page (NO database queries to save usage)"""
        # DISABLED: ErrorLog queries to avoid usage on free tier
        # Users will submit bug reports via feedback instead
        error_id = None

        # DISABLED: Developer notifications to avoid database writes
        # Notifications via feedback submissions only

        # Render custom 500 page (no error ID tracking)
        response = render(request, '500.html', {
            'error_id': error_id,
        }, status=500)

        return response

    def _get_error_message(self, exception):
        """
        Generate a user-friendly error message based on the exception type.

        Returns a helpful message if the error type is recognized, otherwise
        returns a generic error message.
        """
        if exception is None:
            return 'An internal error occurred. Please try again.'

        # Database errors
        if isinstance(exception, DatabaseError):
            return 'A database error occurred. Please try again in a moment.'

        # Integrity errors (e.g., duplicate entries, foreign key violations)
        if isinstance(exception, IntegrityError):
            return 'Unable to complete the operation due to a data conflict. Please check your input and try again.'

        # Validation errors
        if isinstance(exception, ValidationError):
            if hasattr(exception, 'message'):
                return f'Validation error: {exception.message}'
            return 'The data you provided is invalid. Please check and try again.'

        # Object does not exist errors
        if isinstance(exception, ObjectDoesNotExist):
            return 'The requested item could not be found. It may have been deleted.'

        # Value errors (often from data conversion issues)
        if isinstance(exception, ValueError):
            return 'Invalid data provided. Please check your input and try again.'

        # Type errors (often from programming errors, but can be user-triggered)
        if isinstance(exception, TypeError):
            return 'An error occurred processing your request. Please try again.'

        # Key errors (missing expected data)
        if isinstance(exception, KeyError):
            return 'Required information is missing. Please try again.'

        # Generic error for unknown exceptions
        return 'An unexpected error occurred. Our team has been notified. Please try again.'

    def _notify_developers_of_error(self, error_id, request, exception):
        """
        Send notifications to developers when a 500 error occurs.

        Only sends notifications if:
        - Error is not in excluded paths (static files, admin, etc.)
        - Error hasn't been notified about recently (avoid spam)
        """
        try:
            from .notifications import create_notification
            from .models import ErrorLog

            # Skip notification for certain paths
            excluded_paths = ['/static/', '/media/', '/admin/', '/favicon.ico']
            if any(excluded in request.path for excluded in excluded_paths):
                return

            # Check if we've already notified about similar errors recently (last 10 minutes)
            recent_similar = ErrorLog.objects.filter(
                path=request.path,
                error_type__in=['500', 'exception'],
                created_at__gte=timezone.now() - timedelta(minutes=10)
            ).count()

            # Only notify for first occurrence in 10 minutes to avoid spam
            if recent_similar > 1:
                return

            # Get error details
            error_log = ErrorLog.objects.filter(id=error_id).first()
            if not error_log:
                return

            # Get all staff/superuser developers
            developers = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

            # Build notification message
            error_type = type(exception).__name__ if exception else 'Unknown Error'
            error_msg = str(exception)[:100] if exception else 'No details'

            title = f'500 Error: {error_type}'
            message = f'A server error occurred on {request.path}\n\nError: {error_msg}\n\nError ID: {error_id}\n\nUser: {request.user.username if request.user.is_authenticated else "Anonymous"}'

            # Send notification to each developer
            for dev in developers:
                try:
                    create_notification(
                        recipient=dev,
                        notification_type='admin_action',
                        title=title,
                        message=message,
                    )
                except Exception as e:
                    logger.error(f"Failed to notify developer {dev.username}: {e}")

        except Exception as e:
            # Don't let notification errors break error handling
            logger.error(f"Error in _notify_developers_of_error: {e}")

    def _get_500_redirect_target(self, request):
        """
        Determine redirect target for 500 errors.

        For staff users, redirect to admin dashboard.
        For regular users, redirect to home.
        For unauthenticated users, redirect to login.
        """
        user = request.user

        if not user.is_authenticated:
            return 'login'

        if user.is_staff:
            return 'admin_dashboard'

        return 'home'

    def _identify_resource_type(self, path):
        """
        Identify what type of resource is being accessed based on URL path.

        Returns a user-friendly name for the resource type.
        """
        path_lower = path.lower()

        # Check for specific resource types in the path
        if '/machine' in path_lower:
            return 'Machine'
        elif '/queue' in path_lower or '/entry' in path_lower:
            return 'Queue entry'
        elif '/preset' in path_lower:
            return 'Preset'
        elif '/user' in path_lower or '/profile' in path_lower:
            return 'User'
        elif '/appeal' in path_lower:
            return 'Appeal'
        elif '/archive' in path_lower:
            return 'Archive entry'
        elif '/schedule' in path_lower:
            return 'Schedule entry'

        return None

    def _get_redirect_target(self, request, path):
        """
        Determine the appropriate redirect target based on user and context.

        Returns the name of the URL pattern to redirect to.
        """
        user = request.user

        # If user is not authenticated, send to login
        if not user.is_authenticated:
            return 'login'

        # For staff users accessing admin pages
        if user.is_staff:
            path_lower = path.lower()

            # If they were on a user management page
            if '/admin-user' in path_lower or '/approve' in path_lower or '/reject' in path_lower:
                return 'admin_users'

            # If they were on a machine management page
            elif '/admin-machine' in path_lower or '/machine' in path_lower:
                return 'admin_machines'

            # If they were on queue management page
            elif '/admin-queue' in path_lower or '/admin-appeal' in path_lower or '/rush' in path_lower:
                return 'admin_queue'

            # Default for staff: admin dashboard
            else:
                return 'admin_dashboard'

        # For regular users
        else:
            path_lower = path.lower()

            # If they were working with queue entries
            if '/queue' in path_lower or '/entry' in path_lower or '/check' in path_lower:
                return 'my_queue'

            # If they were working with presets
            elif '/preset' in path_lower:
                return 'presets'

            # Default for regular users: home page
            else:
                return 'home'
