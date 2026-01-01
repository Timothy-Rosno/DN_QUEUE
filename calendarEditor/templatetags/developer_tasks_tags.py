from django import template
from django.db.models import Q

register = template.Library()


@register.simple_tag
def get_active_tasks_count():
    """Get count of new + reviewed (current) tasks for developer badge"""
    try:
        from calendarEditor.models import Feedback
        # Count new + reviewed tasks (active tasks that need attention)
        count = Feedback.objects.filter(
            Q(status='new') | Q(status='reviewed')
        ).count()
        return count
    except Exception:
        return 0


@register.simple_tag
def get_pending_users_count():
    """Get count of users pending approval"""
    try:
        from django.contrib.auth.models import User
        count = User.objects.filter(is_active=True, profile__is_approved=False).count()
        return count
    except Exception:
        return 0


@register.simple_tag
def get_rush_jobs_count():
    """Get count of pending queue appeal requests"""
    try:
        from calendarEditor.models import QueueEntry
        # Count entries marked as rush jobs (queue appeals)
        count = QueueEntry.objects.filter(
            is_rush_job=True,
            status='queued'  # Only count queued entries (not completed/cancelled)
        ).count()
        return count
    except Exception:
        return 0


@register.simple_tag
def get_admin_actions_count():
    """Get total count of pending admin actions (users + queue appeals)"""
    return get_pending_users_count() + get_rush_jobs_count()
