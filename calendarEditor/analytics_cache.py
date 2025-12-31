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

    # === ONLINE USERS ===
    online_threshold = now - timedelta(minutes=15)
    online_users_data = []

    recent_views = PageView.objects.filter(
        created_at__gte=online_threshold,
        user__isnull=False
    ).select_related('user', 'user__profile').order_by('-created_at')

    seen_users = set()
    for view in recent_views:
        if view.user_id not in seen_users:
            seen_users.add(view.user_id)
            roles = []
            if view.user.is_superuser:
                roles = ['Admin', 'Developer', 'Staff']
            elif hasattr(view.user, 'profile') and view.user.profile.is_developer:
                roles = ['Developer', 'Staff']
            elif view.user.is_staff:
                roles = ['Staff']
            else:
                roles = ['User']

            online_users_data.append({
                'username': view.user.username,
                'last_seen': view.created_at,
                'roles': roles,
            })

    # === PER-USER STATS ===
    from django.db.models import Count, Max, Q
    all_users = User.objects.select_related('profile').annotate(
        page_views_period=Count('pageview__id', filter=Q(pageview__created_at__gte=start_date) if start_date else Q(), distinct=True),
        page_views_all_time=Count('pageview__id', distinct=True),
        last_seen=Max('pageview__created_at'),
        queue_entries_period=Count('queue_entries__id', filter=Q(queue_entries__created_at__gte=start_date) if start_date else Q(), distinct=True),
        queue_entries_all_time=Count('queue_entries__id', distinct=True),
        feedback_submitted_period=Count('feedback_submissions__id', filter=Q(feedback_submissions__created_at__gte=start_date) if start_date else Q(), distinct=True),
    )

    per_user_stats = []
    for user in all_users:
        roles = []
        if user.is_superuser:
            roles = ['Admin', 'Developer', 'Staff']
        elif hasattr(user, 'profile') and user.profile.is_developer:
            roles = ['Developer', 'Staff']
        elif user.is_staff:
            roles = ['Staff']
        else:
            roles = ['User']

        per_user_stats.append({
            'username': user.username,
            'email': user.email,
            'roles': roles,
            'last_seen': user.last_seen,
            'page_views_period': user.page_views_period,
            'page_views_all_time': user.page_views_all_time,
            'queue_entries_period': user.queue_entries_period,
            'queue_entries_all_time': user.queue_entries_all_time,
            'feedback_submitted_period': user.feedback_submitted_period,
            'is_online': user.last_seen and user.last_seen >= online_threshold,
        })

    per_user_stats.sort(key=lambda x: x['last_seen'] if x['last_seen'] else timezone.datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    top_10_users = per_user_stats[:10]

    # === SESSION & RETENTION METRICS ===
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    dau = PageView.objects.filter(created_at__gte=today_start, user__isnull=False).values('user').distinct().count()
    wau = PageView.objects.filter(created_at__gte=week_start, user__isnull=False).values('user').distinct().count()
    mau = PageView.objects.filter(created_at__gte=month_start, user__isnull=False).values('user').distinct().count()

    new_users_period = User.objects.filter(date_joined__gte=start_date).count() if start_date else 0
    returning_users = page_views_filtered.filter(user__isnull=False).exclude(user__date_joined__gte=start_date).values('user').distinct().count() if start_date else 0

    # === QUEUE METRICS ===
    completed_entries = queue_filtered.filter(status='completed', updated_at__isnull=False).order_by('-updated_at')[:1000]
    wait_times = []
    for entry in completed_entries:
        wait_time = (entry.updated_at - entry.created_at).total_seconds() / 3600
        if wait_time < 168:
            wait_times.append(wait_time)
    avg_queue_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0

    total_queue = queue_filtered.count()
    completed_queue = queue_filtered.filter(status='completed').count()
    queue_completion_rate = (completed_queue / total_queue * 100) if total_queue > 0 else 0

    popular_machines = queue_filtered.filter(assigned_machine__isnull=False).values('assigned_machine__name').annotate(count=Count('id')).order_by('-count')[:5]

    # === FEEDBACK RESPONSE TIME ===
    feedback_reviewed = Feedback.objects.filter(status__in=['reviewed', 'completed'], reviewed_at__isnull=False).order_by('-reviewed_at')[:500]
    review_times = []
    for fb in feedback_reviewed:
        time_diff = (fb.reviewed_at - fb.created_at).total_seconds() / 3600
        if time_diff < 720:
            review_times.append(time_diff)
    avg_feedback_review_time = sum(review_times) / len(review_times) if review_times else 0

    feedback_completed = Feedback.objects.filter(status='completed', reviewed_at__isnull=False, updated_at__isnull=False).order_by('-updated_at')[:500]
    completion_times = []
    for fb in feedback_completed:
        time_diff = (fb.updated_at - fb.reviewed_at).total_seconds() / 3600
        if time_diff < 720:
            completion_times.append(time_diff)
    avg_feedback_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0

    # === ERROR STATISTICS ===
    error_logs_filtered = ErrorLog.objects.all()
    if start_date:
        error_logs_filtered = error_logs_filtered.filter(created_at__gte=start_date)

    total_errors = error_logs_filtered.count()
    error_404_count = error_logs_filtered.filter(error_type='404').count()
    error_500_count = error_logs_filtered.filter(error_type='500').count()
    error_403_count = error_logs_filtered.filter(error_type='403').count()
    top_error_paths = error_logs_filtered.values('path', 'error_type').annotate(count=Count('id')).order_by('-count')[:10]
    recent_errors = error_logs_filtered.select_related('user').order_by('-created_at')[:10]

    # === HOURLY/DAILY CHARTS ===
    from django.db.models import Func, IntegerField

    class Hour(Func):
        function = 'CAST'
        template = "%(function)s(strftime('%%H', %(expressions)s) AS INTEGER)"
        output_field = IntegerField()

    class Weekday(Func):
        function = 'CAST'
        template = "%(function)s(strftime('%%w', %(expressions)s) AS INTEGER)"
        output_field = IntegerField()

    hourly_views = page_views_filtered.annotate(hour=Hour('created_at')).values('hour').annotate(count=Count('id')).order_by('hour')
    hour_labels = [f"{h['hour']}:00" for h in hourly_views]
    hour_counts = [h['count'] * 10 for h in hourly_views]  # Scale up from 10% sample

    daily_views = page_views_filtered.annotate(weekday=Weekday('created_at')).values('weekday').annotate(count=Count('id')).order_by('weekday')
    day_map = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday'}
    day_labels = [day_map.get(d['weekday'], 'Unknown') for d in daily_views]
    day_counts = [d['count'] * 10 for d in daily_views]  # Scale up from 10% sample

    # === API HITS ===
    api_hits = {
        'API Machine Status': page_views_filtered.filter(path__contains='api/machine-status').count() * 10,
        'Notifications API': page_views_filtered.filter(path__contains='notifications/api/list').count() * 10,
        'Schedule API': page_views_filtered.filter(path__contains='schedule/api').count() * 10,
    }

    # === SESSION DURATION ===
    from django.db.models import Min
    sessions = page_views_filtered.values('session_key').annotate(
        first_view=Min('created_at'),
        last_view=Max('created_at'),
        view_count=Count('id')
    ).filter(view_count__gt=1).order_by('-last_view')[:5000]

    session_durations = []
    for session in sessions:
        duration = (session['last_view'] - session['first_view']).total_seconds() / 60
        if duration < 120:
            session_durations.append(duration)
    avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0

    # Get Turso database usage metrics
    import os
    from .turso_api_client import TursoAPIClient

    turso_client = TursoAPIClient()
    turso_usage = turso_client.get_usage_metrics()

    # Turso plan limits (Free tier defaults)
    turso_limits = {
        'storage_mb': int(os.environ.get('TURSO_MAX_STORAGE_MB', 5120)),  # 5GB
        'rows_read_monthly': int(os.environ.get('TURSO_MAX_ROWS_READ', 500_000_000)),  # 500M
        'rows_written_monthly': int(os.environ.get('TURSO_MAX_ROWS_WRITTEN', 10_000_000)),  # 10M
    }

    # Calculate usage percentages
    turso_stats = None
    if turso_usage:
        turso_stats = {
            'rows_read': turso_usage['rows_read'],
            'rows_written': turso_usage['rows_written'],
            'storage_mb': turso_usage['storage_bytes'] / (1024 * 1024),
            'databases': turso_usage.get('databases', 0),
            'rows_read_percent': (turso_usage['rows_read'] / turso_limits['rows_read_monthly'] * 100),
            'rows_written_percent': (turso_usage['rows_written'] / turso_limits['rows_written_monthly'] * 100),
            'storage_percent': (turso_usage['storage_bytes'] / (turso_limits['storage_mb'] * 1024 * 1024) * 100),
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

        # Turso database stats
        'turso_usage': turso_stats,
        'turso_limits': turso_limits,
        'turso_org_slug': os.environ.get('TURSO_ORG_SLUG', 'unknown'),

        # Online users and per-user stats
        'online_users_data': online_users_data,
        'per_user_stats': per_user_stats,
        'top_10_users': top_10_users,

        # API hits
        'api_hits': api_hits,

        # Peak usage times (charts)
        'hour_labels': hour_labels,
        'hour_counts': hour_counts,
        'day_labels': day_labels,
        'day_counts': day_counts,

        # Session metrics
        'avg_session_duration': round(avg_session_duration, 2),

        # User retention
        'dau': dau,
        'wau': wau,
        'mau': mau,
        'new_users_period': new_users_period,
        'returning_users': returning_users,

        # Queue metrics
        'avg_queue_wait_time': round(avg_queue_wait_time, 2),
        'queue_completion_rate': round(queue_completion_rate, 1),
        'popular_machines': popular_machines,

        # Feedback response time
        'avg_feedback_review_time': round(avg_feedback_review_time, 2),
        'avg_feedback_completion_time': round(avg_feedback_completion_time, 2),

        # Error statistics
        'total_errors': total_errors,
        'error_404_count': error_404_count,
        'error_500_count': error_500_count,
        'error_403_count': error_403_count,
        'top_error_paths': top_error_paths,
        'recent_errors': recent_errors,
    }

    # Cache for 24 hours (expires at midnight)
    tomorrow = today + timedelta(days=1)
    seconds_until_midnight = (datetime.combine(tomorrow, datetime.min.time()) - datetime.now()).total_seconds()
    cache.set(cache_key, analytics_data, int(seconds_until_midnight))

    print(f"✅ Analytics calculated and cached until midnight")

    return analytics_data
