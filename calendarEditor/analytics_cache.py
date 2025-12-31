"""
Simple lazy-evaluated analytics with daily caching.

Calculates stats ONCE per day on first /data visit, then caches for 24 hours.
No scheduled jobs needed - only calculates when someone actually views the dashboard.
"""
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Count, Max, Min, Q
from collections import Counter


def get_daily_analytics(days_filter=30):
    """
    Get analytics data with smart caching.

    - Calculates ONCE per day on first request
    - Caches for 24 hours
    - Subsequent requests read from cache (instant!)

    Args:
        days_filter: Number of days to analyze (0 = all time, 7 = last week, 30 = last month)

    Returns:
        dict: Complete analytics data ready for dashboard
    """
    from .models import PageView, QueueEntry, User, Feedback, ErrorLog
    from .analytics_utils import get_set_size, get_sorted_set_count

    # Cache key includes filter to support different views
    today = datetime.now().date()
    cache_key = f'analytics_daily_{days_filter}_{today}'

    # Try to get from cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        print(f"✅ Using cached analytics for {today} (filter: {days_filter} days)")
        return cached_data

    print(f"📊 Calculating fresh analytics for {today} (filter: {days_filter} days)...")

    # Calculate fresh data (only happens once per day)
    now = timezone.now()

    if days_filter == 0:
        start_date = None
        day_start = None
    else:
        start_date = now - timedelta(days=days_filter)
        day_start = datetime.combine(today, datetime.min.time())

    # === TODAY'S REAL-TIME STATS (from cache) ===
    today_views = cache.get(f'analytics:pageviews:{today}', 0)
    today_users = get_set_size(f'analytics:users:{today}')
    today_sessions = get_set_size(f'analytics:sessions:{today}')
    users_online_now = get_sorted_set_count('analytics:users_online', now.timestamp() - 900)  # Last 15 min

    # === PERIOD STATS (database queries) ===
    # Page views from sampled data (extrapolate from 10% sample)
    page_views_query = PageView.objects.all()
    if start_date:
        page_views_filtered = page_views_query.filter(created_at__gte=start_date)
    else:
        page_views_filtered = page_views_query

    sampled_count = page_views_filtered.count()
    page_views_period = sampled_count * 10  # We only store 10%, so multiply by 10
    page_views_all_time = page_views_query.count() * 10

    # Top pages (from cache counters for today, DB for historical)
    top_pages_data = []
    for page_title in ['Home', 'Submit Request', 'My Queue', 'Public Queue',
                       'Check-In/Check-Out', 'Archive', 'Fridge Specs']:
        count = cache.get(f'analytics:page:{page_title}:{today}', 0)
        if count > 0:
            top_pages_data.append({'page_title': page_title, 'count': count})

    # Sort and limit
    top_pages = sorted(top_pages_data, key=lambda x: x['count'], reverse=True)[:10]

    # Queue stats
    queue_all = QueueEntry.objects.all()
    if start_date:
        queue_filtered = queue_all.filter(created_at__gte=start_date)
    else:
        queue_filtered = queue_all

    queue_stats = {
        'total_period': queue_filtered.count(),
        'total_all_time': queue_all.count(),
        'completed_period': queue_filtered.filter(status='completed').count(),
        'completed_all_time': queue_all.filter(status='completed').count(),
    }

    # Feedback stats
    feedback_all = Feedback.objects.all()
    if start_date:
        feedback_filtered = feedback_all.filter(created_at__gte=start_date)
    else:
        feedback_filtered = feedback_all

    feedback_stats = {
        'total': feedback_all.count(),
        'total_period': feedback_filtered.count(),
        'new': feedback_all.filter(status='new').count(),
        'reviewed': feedback_all.filter(status='reviewed').count(),
        'completed': feedback_all.filter(status='completed').count(),
    }

    # Calculate active users for the period (before slicing)
    if days_filter <= 1:
        active_period = today_users
    else:
        active_period = page_views_filtered.filter(user__isnull=False).values('user').distinct().count()

    # Device/Browser breakdown from sampled data
    device_counts = {'mobile': 0, 'desktop': 0, 'tablet': 0}
    browser_counts = Counter()

    sampled_views = page_views_filtered.all()[:5000]  # Sample max 5000 for efficiency

    for pv in sampled_views:
        if isinstance(pv.device_info, dict):
            # Device
            if pv.device_info.get('is_mobile'):
                device_counts['mobile'] += 1
            elif pv.device_info.get('is_tablet'):
                device_counts['tablet'] += 1
            elif pv.device_info.get('is_pc'):
                device_counts['desktop'] += 1

            # Browser
            browser = pv.device_info.get('browser', 'Unknown')
            browser_parts = browser.split()
            if browser_parts:
                if browser_parts[0] == 'Mobile' and len(browser_parts) > 1:
                    browser_family = browser_parts[1]
                elif len(browser_parts) > 1 and browser_parts[-1] == 'Mobile':
                    browser_family = browser_parts[0]
                else:
                    browser_family = browser_parts[0]

                if browser_family not in {'Mobile', 'Other', 'Unknown', 'Generic', 'Tablet', 'Desktop', 'Android', 'iPhone', 'iPad'}:
                    browser_counts[browser_family] += 1

    # Scale up from sample
    device_breakdown = {k: v * 10 for k, v in device_counts.items()}
    top_browsers = browser_counts.most_common(5)
    browser_device_stats = browser_counts.most_common(10)

    # User stats
    user_types = {
        'total': User.objects.count(),
        'staff': User.objects.filter(is_staff=True).count(),
        'developers': User.objects.filter(profile__is_developer=True).count(),
        'active_period': active_period,
    }

    # === BUILD RESPONSE DATA ===
    analytics_data = {
        # Real-time (today)
        'users_online': users_online_now,
        'today_views': today_views,
        'today_users': today_users,

        # Period stats
        'days_filter': days_filter,
        'page_views_period': page_views_period,
        'page_views_all_time': page_views_all_time,
        'top_pages': top_pages,
        'queue_stats': queue_stats,
        'feedback_stats': feedback_stats,
        'user_types': user_types,
        'device_breakdown': device_breakdown,
        'top_browsers': top_browsers,
        'browser_device_stats': browser_device_stats,

        # Empty placeholders for features we removed
        'online_users_data': [],
        'per_user_stats': [],
        'api_hits': {},
        'hour_labels': [],
        'hour_counts': [],
        'day_labels': [],
        'day_counts': [],
        'avg_session_duration': 0,
        'dau': today_users,
        'wau': 0,
        'mau': 0,
        'new_users_period': 0,
        'returning_users': 0,
        'avg_queue_wait_time': 0,
        'queue_completion_rate': 0,
        'popular_machines': [],
        'top_10_users': [],
        'avg_feedback_review_time': 0,
        'avg_feedback_completion_time': 0,
        'total_errors': 0,
        'error_404_count': 0,
        'error_500_count': 0,
        'error_403_count': 0,
        'top_error_paths': [],
        'recent_errors': [],
        'turso_stats': None,
    }

    # Cache for 24 hours (expires at midnight)
    tomorrow = today + timedelta(days=1)
    seconds_until_midnight = (datetime.combine(tomorrow, datetime.min.time()) - datetime.now()).total_seconds()
    cache.set(cache_key, analytics_data, int(seconds_until_midnight))

    print(f"✅ Analytics calculated and cached until midnight")

    return analytics_data
