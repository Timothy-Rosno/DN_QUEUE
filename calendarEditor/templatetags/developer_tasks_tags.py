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
        # Count users where profile status is 'pending' (not approved or rejected)
        pending_users = User.objects.filter(is_active=True, profile__status='pending')
        count = pending_users.count()
        if count > 0:
            print(f"[PENDING_USERS] Found {count} pending users:")
            for user in pending_users:
                print(f"  - {user.username}: status={user.profile.status}, is_approved={user.profile.is_approved}")
        return count
    except Exception as e:
        print(f"[PENDING_USERS] Error: {e}")
        return 0


@register.simple_tag
def get_rush_jobs_count():
    """Get count of pending queue appeal requests"""
    try:
        from calendarEditor.models import QueueEntry
        # Count entries marked as rush jobs (queue appeals)
        rush_jobs = QueueEntry.objects.filter(
            is_rush_job=True,
            status='queued'  # Only count queued entries (not completed/cancelled)
        )
        count = rush_jobs.count()
        if count > 0:
            print(f"[RUSH_JOBS] Found {count} rush jobs:")
            for entry in rush_jobs:
                print(f"  - {entry.title} by {entry.user.username} (is_rush_job={entry.is_rush_job}, status={entry.status})")
        return count
    except Exception as e:
        print(f"[RUSH_JOBS] Error: {e}")
        return 0


@register.simple_tag
def get_admin_actions_count():
    """Get total count of pending admin actions (users + queue appeals)"""
    return get_pending_users_count() + get_rush_jobs_count()
