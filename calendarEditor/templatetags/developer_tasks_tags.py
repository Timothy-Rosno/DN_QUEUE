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
