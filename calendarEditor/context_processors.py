"""
Context processors for making data available to all templates.
"""

def check_in_out_count(request):
    """
    Add check-in/check-out count to all template contexts.
    This counts:
    - Ready-to-check-in entries (position 1 AND machine is idle)
    - Running entries (can be checked out)
    """
    if not request.user.is_authenticated:
        return {'check_in_out_count': 0}

    from .models import QueueEntry

    # Count ready-to-check-in entries (position 1 AND machine is idle)
    ready_to_check_in_count = QueueEntry.objects.filter(
        user=request.user,
        status='queued',
        queue_position=1,
        assigned_machine__current_status='idle'
    ).count()

    # Count running entries (can check out)
    running_count = QueueEntry.objects.filter(
        user=request.user,
        status='running'
    ).count()

    total_count = ready_to_check_in_count + running_count

    return {'check_in_out_count': total_count}
