"""
Context processors for making data available to all templates.
"""

def check_in_out_count(request):
    """
    Add check-in/check-out count to all template contexts.
    This counts:
    - Ready-to-check-in entries (position 1 AND machine is idle)
    - Running entries (can be checked out)

    OPTIMIZATION: Cached for 10 seconds per user to prevent DB hammering.
    This context processor runs on EVERY page render!
    """
    if not request.user.is_authenticated:
        return {'check_in_out_count': 0}

    from django.core.cache import cache
    from .models import QueueEntry

    # Cache key specific to this user
    cache_key = f'check_in_out_count_user_{request.user.id}'

    # Try to get cached value first
    cached_count = cache.get(cache_key)
    if cached_count is not None:
        return {'check_in_out_count': cached_count}

    # Cache miss - query database
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

    # Cache for 10 seconds
    cache.set(cache_key, total_count, 10)

    return {'check_in_out_count': total_count}
