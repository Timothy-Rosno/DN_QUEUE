"""
Views for error handling and debugging.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import ErrorLog
from .notifications import create_notification
from django.contrib.auth.models import User


@login_required
def error_detail(request, error_id):
    """
    Display detailed information about a specific error.
    Only accessible to staff/admin users.
    """
    # Only staff can view error details
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to view error details.')
        return redirect('home')

    # Get the error log entry
    error = get_object_or_404(ErrorLog, id=error_id)

    # Find similar errors (same path and error type in last 24 hours)
    similar_errors = ErrorLog.objects.filter(
        path=error.path,
        error_type=error.error_type,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).exclude(id=error.id).order_by('-created_at')

    # Check if this is a recent pattern (3+ errors in last hour)
    recent_count = ErrorLog.objects.filter(
        path=error.path,
        error_type=error.error_type,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()

    context = {
        'error': error,
        'similar_errors': similar_errors,
        'similar_errors_count': similar_errors.count(),
        'recently_occurred': recent_count >= 3,
    }

    return render(request, 'error_detail.html', context)


@login_required
def notify_error(request, error_id):
    """
    Send a Slack notification to developers about a specific error.
    Only accessible to staff/admin users.
    """
    # Only staff can trigger error notifications
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to send error notifications.')
        return redirect('home')

    # Get the error log entry
    error = get_object_or_404(ErrorLog, id=error_id)

    # Get all staff/superuser developers
    developers = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

    # Send notification to each developer
    notified_count = 0
    for dev in developers:
        # Skip the current user (they already know about the error)
        if dev.id == request.user.id:
            continue

        try:
            create_notification(
                recipient=dev,
                notification_type='admin_action',
                title=f'Error Alert: {error.get_error_type_display()}',
                message=f'{request.user.username} flagged error #{error.id} for attention.\n\nPath: {error.path}\nStatus: {error.status_code}\nMessage: {error.error_message[:200]}',
            )
            notified_count += 1
        except Exception as e:
            print(f"Failed to notify {dev.username}: {e}")
            continue

    if notified_count > 0:
        messages.success(request, f'Error notification sent to {notified_count} developer(s).')
    else:
        messages.warning(request, 'No developers were notified.')

    return redirect('error_detail', error_id=error_id)
