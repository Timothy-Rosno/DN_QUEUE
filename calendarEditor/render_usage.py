"""
Render Usage Tracking Utilities

Tracks usage metrics against Render's free tier limits:
- Web Service: 750 hours/month
- PostgreSQL: 1GB storage (tracked separately in storage_utils.py)
"""
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta


def get_cache_key_for_month(year, month):
    """Generate cache key for a specific month's request count."""
    return f'render_requests_{year}_{month:02d}'


def increment_request_count():
    """
    Increment the request counter for the current month.
    Uses Django cache to store counts efficiently.

    Gracefully handles Redis connection failures to prevent app crashes.
    """
    try:
        now = timezone.now()
        cache_key = get_cache_key_for_month(now.year, now.month)

        # Increment counter, default to 1 if doesn't exist
        # Timeout set to 45 days to persist across month boundary
        current = cache.get(cache_key, 0)
        cache.set(cache_key, current + 1, timeout=60*60*24*45)
    except Exception as e:
        # Log but don't crash - Redis may be unavailable during cold starts
        print(f"Warning: Could not increment request count: {e}")
        pass


def get_monthly_request_count():
    """
    Get total requests for the current month.

    Returns 0 if Redis is unavailable.
    """
    try:
        now = timezone.now()
        cache_key = get_cache_key_for_month(now.year, now.month)
        return cache.get(cache_key, 0)
    except Exception as e:
        # Return 0 if Redis is unavailable
        print(f"Warning: Could not get monthly request count: {e}")
        return 0


def get_render_usage_stats():
    """
    Get comprehensive Render usage statistics.

    Returns:
        dict: Usage stats including requests, estimated uptime, etc.
    """
    now = timezone.now()

    # Get request count for current month
    requests_this_month = get_monthly_request_count()

    # Estimate uptime hours
    # Render free tier: 750 hours/month limit
    # Since we have GitHub Actions pinging every 5 minutes, server stays up ~24/7
    # Calculate days elapsed this month
    days_this_month = now.day

    # Conservative estimate: assume ~23.5 hours/day uptime (accounting for some downtime)
    estimated_uptime_hours = days_this_month * 23.5

    # Render limits
    max_uptime_hours = 750
    uptime_percentage = min((estimated_uptime_hours / max_uptime_hours) * 100, 100)

    # Determine status
    if uptime_percentage >= 95:
        status = 'critical'
    elif uptime_percentage >= 80:
        status = 'warning'
    else:
        status = 'ok'

    # Calculate days remaining in month
    if now.month == 12:
        next_month = timezone.make_aware(datetime(now.year + 1, 1, 1))
    else:
        next_month = timezone.make_aware(datetime(now.year, now.month + 1, 1))

    days_remaining = (next_month - now.replace(hour=0, minute=0, second=0, microsecond=0)).days

    return {
        'requests_this_month': requests_this_month,
        'estimated_uptime_hours': round(estimated_uptime_hours, 1),
        'max_uptime_hours': max_uptime_hours,
        'uptime_percentage': round(uptime_percentage, 1),
        'hours_remaining': round(max_uptime_hours - estimated_uptime_hours, 1),
        'days_this_month': days_this_month,
        'days_remaining': days_remaining,
        'status': status,
    }
