"""
Error Handling Middleware for Calendar Editor

Catches 404, 403, and 500 errors globally and redirects users to appropriate pages
with helpful error messages.
"""

from django.http import Http404
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve
from django.db import DatabaseError, IntegrityError
import logging

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
        """Handle 404 errors with context-aware redirects"""
        # Determine what resource was being accessed based on URL path
        path = request.path
        resource_type = self._identify_resource_type(path)

        # Create helpful error message
        if resource_type:
            messages.error(
                request,
                f'{resource_type} not found. It may have been deleted or you may not have access to it.'
            )
        else:
            messages.error(request, 'The page you requested could not be found.')

        # Redirect to appropriate page
        return redirect(self._get_redirect_target(request, path))

    def _handle_403(self, request):
        """Handle permission denied errors with context-aware redirects"""
        path = request.path
        resource_type = self._identify_resource_type(path)

        # Create helpful error message
        if resource_type:
            messages.error(
                request,
                f'You do not have permission to access this {resource_type.lower()}.'
            )
        else:
            messages.error(request, 'You do not have permission to access this page.')

        # Redirect to appropriate page
        return redirect(self._get_redirect_target(request, path))

    def _handle_500(self, request, exception):
        """Handle 500 errors with helpful error messages"""
        # For developers/staff, show detailed error information
        if request.user.is_authenticated and (request.user.is_staff or hasattr(request.user, 'profile') and getattr(request.user.profile, 'is_developer', False)):
            if exception:
                error_message = f'Developer Debug: {type(exception).__name__}: {str(exception)}'
            else:
                error_message = 'Developer Debug: 500 Internal Server Error (no exception details available)'
        else:
            # For regular users, show user-friendly message
            error_message = self._get_error_message(exception)

        # Show error message to user
        messages.error(request, error_message)

        # Redirect to appropriate page (usually home)
        return redirect(self._get_500_redirect_target(request))

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
