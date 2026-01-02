"""
Custom decorators for calendarEditor views.

Provides unified validation, permission checking, and transaction handling
for queue management views.
"""
from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction


def developer_required(view_func):
    """
    Decorator to require developer role access.

    Checks if the user is a developer or superuser.
    Redirects to home with error message if not authorized.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Check if user has profile
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'Developer access required.')
            return redirect('home')

        # Check if user is developer or superuser
        if not (request.user.profile.is_developer or request.user.is_superuser):
            messages.error(request, 'Developer access required.')
            return redirect('home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def require_queue_status(*allowed_statuses, redirect_to='my_queue', allow_staff=False):
    """
    Decorator to ensure queue entry is in an allowed status before action.

    Validates that:
    1. Queue entry exists
    2. User owns the entry (or is staff if allow_staff=True)
    3. Entry status is in allowed_statuses

    Args:
        *allowed_statuses: Tuple of allowed status values ('queued', 'running', etc.)
        redirect_to: URL name to redirect to on error (default: 'my_queue')
        allow_staff: Whether staff can act on any entry (default: False)

    Usage:
        @require_queue_status('queued')
        def check_in_job(request, queue_entry):
            # queue_entry is guaranteed to be 'queued' and owned by user
            ...

        @require_queue_status('running', 'queued', allow_staff=True)
        def admin_cancel_entry(request, queue_entry):
            # Staff can cancel running or queued entries
            ...

    Note: The decorated view receives 'queue_entry' as a parameter instead of 'entry_id'.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, entry_id, *args, **kwargs):
            # Import here to avoid circular imports
            from .models import QueueEntry

            # Get queue entry or return 404
            queue_entry = get_object_or_404(QueueEntry, id=entry_id)

            # Permission check - user must own entry unless staff override
            if queue_entry.user != request.user:
                if not (allow_staff and request.user.is_staff):
                    messages.error(request, 'Permission denied: This entry belongs to another user.')
                    return redirect('home')

            # Status check
            if queue_entry.status not in allowed_statuses:
                status_list = ', '.join(f"'{s}'" for s in allowed_statuses)
                messages.error(
                    request,
                    f'Cannot perform this action - entry is currently "{queue_entry.get_status_display()}". '
                    f'Expected status: {status_list}'
                )
                return redirect(redirect_to)

            # Pass queue_entry to view to avoid re-fetching
            return view_func(request, queue_entry, *args, **kwargs)

        return wrapper
    return decorator


def require_machine_available(redirect_to='check_in_check_out'):
    """
    Decorator to ensure assigned machine is available before action.

    Validates that:
    1. Queue entry has an assigned machine
    2. Machine is marked as available
    3. Machine is not in maintenance
    4. Machine doesn't have another running job

    Args:
        redirect_to: URL name to redirect to on error (default: 'check_in_check_out')

    Usage:
        @require_queue_status('queued')
        @require_machine_available()
        def check_in_job(request, queue_entry):
            # queue_entry.assigned_machine is guaranteed to be available
            ...

    Note: Must be used AFTER require_queue_status decorator (needs queue_entry param).
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, queue_entry, *args, **kwargs):
            # Import here to avoid circular imports
            from .models import QueueEntry

            machine = queue_entry.assigned_machine

            # Check machine exists
            if not machine:
                messages.error(request, 'Cannot proceed: No machine assigned to this entry.')
                return redirect(redirect_to)

            # Check machine availability flag
            if not machine.is_available:
                messages.error(request, f'Cannot proceed: {machine.name} is currently marked as unavailable.')
                return redirect(redirect_to)

            # Check machine maintenance status
            if machine.current_status == 'maintenance':
                messages.error(request, f'Cannot proceed: {machine.name} is currently under maintenance.')
                return redirect(redirect_to)

            # Check for conflicting running jobs (unless this is the running job)
            conflict = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='running'
            ).exclude(id=queue_entry.id).first()

            if conflict:
                messages.error(
                    request,
                    f'Cannot proceed: {machine.name} is currently busy with another job '
                    f'(Entry #{conflict.id}: "{conflict.title}").'
                )
                return redirect(redirect_to)

            return view_func(request, queue_entry, *args, **kwargs)

        return wrapper
    return decorator


def atomic_operation(view_func):
    """
    Decorator that wraps view in atomic database transaction.

    Ensures all database operations in the view succeed or fail together.
    Automatically rolls back on exceptions.

    Usage:
        @require_queue_status('queued')
        @atomic_operation
        def check_in_job(request, queue_entry):
            # All database changes here are atomic
            queue_entry.status = 'running'
            queue_entry.save()
            # If this fails, the status change is rolled back
            send_notification(queue_entry.user, "Checked in")
            ...

    Note: Can be combined with other decorators. Place it closest to the view function.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        with transaction.atomic():
            return view_func(request, *args, **kwargs)

    return wrapper


def require_own_entry(redirect_to='my_queue'):
    """
    Decorator to ensure user owns the queue entry.

    Simpler version of require_queue_status when you only need ownership check.

    Args:
        redirect_to: URL name to redirect to on error (default: 'my_queue')

    Usage:
        @require_own_entry()
        def view_entry_details(request, queue_entry):
            # queue_entry is guaranteed to belong to request.user
            ...

    Note: The decorated view receives 'queue_entry' as a parameter instead of 'entry_id'.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, entry_id, *args, **kwargs):
            # Import here to avoid circular imports
            from .models import QueueEntry

            # Get queue entry or return 404
            queue_entry = get_object_or_404(QueueEntry, id=entry_id)

            # Permission check
            if queue_entry.user != request.user:
                messages.error(request, 'Permission denied: This entry belongs to another user.')
                return redirect('home')

            # Pass queue_entry to view
            return view_func(request, queue_entry, *args, **kwargs)

        return wrapper
    return decorator
