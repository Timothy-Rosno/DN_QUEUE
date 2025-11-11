"""
Database storage utilities for monitoring and managing database size.
"""
from django.db import connection
from django.conf import settings
from pathlib import Path
import os


def get_table_row_count(model):
    """Get the row count for a given model."""
    try:
        return model.objects.count()
    except:
        return 0


def estimate_table_size_mb(model, avg_row_size_kb=1.5):
    """
    Estimate table size based on row count.
    Uses average row size estimate (default 1.5 KB per row for typical Django tables).
    """
    row_count = get_table_row_count(model)
    size_mb = (row_count * avg_row_size_kb) / 1024
    return round(size_mb, 2)


def get_uploaded_files_size_mb():
    """Calculate total size of uploaded files in media directory."""
    try:
        media_root = settings.MEDIA_ROOT
        total_size = 0

        for dirpath, dirnames, filenames in os.walk(media_root):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)

        return round(total_size / (1024 * 1024), 2)
    except:
        return 0


def get_storage_breakdown():
    """
    Get detailed breakdown of database storage by table/category.

    Returns:
        dict: Storage breakdown with sizes and row counts
    """
    from django.contrib.auth.models import User
    from calendarEditor.models import (
        Machine, QueueEntry, QueuePreset, ArchivedMeasurement,
        Notification, NotificationPreference, OneTimeLoginToken
    )
    from userRegistration.models import UserProfile

    breakdown = {
        'users': {
            'name': 'User Accounts',
            'row_count': get_table_row_count(User),
            'estimated_size_mb': estimate_table_size_mb(User, avg_row_size_kb=2),
        },
        'user_profiles': {
            'name': 'User Profiles',
            'row_count': get_table_row_count(UserProfile),
            'estimated_size_mb': estimate_table_size_mb(UserProfile, avg_row_size_kb=1),
        },
        'machines': {
            'name': 'Machines',
            'row_count': get_table_row_count(Machine),
            'estimated_size_mb': estimate_table_size_mb(Machine, avg_row_size_kb=2),
        },
        'queue_entries': {
            'name': 'Queue Entries',
            'row_count': get_table_row_count(QueueEntry),
            'estimated_size_mb': estimate_table_size_mb(QueueEntry, avg_row_size_kb=3),
        },
        'presets': {
            'name': 'Queue Presets',
            'row_count': get_table_row_count(QueuePreset),
            'estimated_size_mb': estimate_table_size_mb(QueuePreset, avg_row_size_kb=2),
        },
        'archived_measurements': {
            'name': 'Archived Measurements (Records)',
            'row_count': get_table_row_count(ArchivedMeasurement),
            'estimated_size_mb': estimate_table_size_mb(ArchivedMeasurement, avg_row_size_kb=2),
        },
        'uploaded_files': {
            'name': 'Uploaded Files (Media)',
            'row_count': ArchivedMeasurement.objects.filter(uploaded_file__isnull=False).count(),
            'estimated_size_mb': get_uploaded_files_size_mb(),
        },
        'notifications': {
            'name': 'Notifications',
            'row_count': get_table_row_count(Notification),
            'estimated_size_mb': estimate_table_size_mb(Notification, avg_row_size_kb=1),
        },
        'notification_preferences': {
            'name': 'Notification Preferences',
            'row_count': get_table_row_count(NotificationPreference),
            'estimated_size_mb': estimate_table_size_mb(NotificationPreference, avg_row_size_kb=0.5),
        },
        'login_tokens': {
            'name': 'One-Time Login Tokens',
            'row_count': get_table_row_count(OneTimeLoginToken),
            'estimated_size_mb': estimate_table_size_mb(OneTimeLoginToken, avg_row_size_kb=0.5),
        },
    }

    # Calculate total
    total_estimated_mb = sum(item['estimated_size_mb'] for item in breakdown.values())

    # Add percentage to each item
    for item in breakdown.values():
        if total_estimated_mb > 0:
            item['percentage'] = round((item['estimated_size_mb'] / total_estimated_mb) * 100, 1)
        else:
            item['percentage'] = 0

    return {
        'breakdown': breakdown,
        'total_estimated_mb': round(total_estimated_mb, 2),
    }


def get_database_size_mb():
    """
    Get the current database size in megabytes.

    Returns:
        float: Database size in MB, or None if unable to determine
    """
    db_engine = settings.DATABASES['default']['ENGINE']

    try:
        if 'postgresql' in db_engine:
            # PostgreSQL
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_database_size(current_database());")
                size_bytes = cursor.fetchone()[0]
                return size_bytes / (1024 * 1024)  # Convert to MB

        elif 'sqlite' in db_engine:
            # SQLite
            db_path = settings.DATABASES['default']['NAME']
            if os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                return size_bytes / (1024 * 1024)  # Convert to MB
            return 0.0

        else:
            # Unknown database type
            return None

    except Exception as e:
        print(f"Error getting database size: {e}")
        return None


def get_storage_stats():
    """
    Get comprehensive storage statistics.

    Returns:
        dict: {
            'current_size_mb': float,
            'max_size_mb': int,
            'used_percentage': float,
            'available_mb': float,
            'status': str ('ok', 'warning', 'critical'),
            'warning_threshold': float
        }
    """
    current_size = get_database_size_mb()
    max_size = getattr(settings, 'MAX_DATABASE_SIZE_MB', 1024)
    warning_threshold = getattr(settings, 'STORAGE_WARNING_THRESHOLD', 0.80)

    if current_size is None:
        return {
            'current_size_mb': 0,
            'max_size_mb': max_size,
            'used_percentage': 0,
            'available_mb': max_size,
            'status': 'unknown',
            'warning_threshold': warning_threshold,
            'error': 'Unable to determine database size'
        }

    used_percentage = (current_size / max_size) if max_size > 0 else 0
    available_mb = max(0, max_size - current_size)

    # Determine status
    if used_percentage >= 0.95:
        status = 'critical'
    elif used_percentage >= warning_threshold:
        status = 'warning'
    else:
        status = 'ok'

    return {
        'current_size_mb': round(current_size, 2),
        'max_size_mb': max_size,
        'used_percentage': round(used_percentage * 100, 1),
        'available_mb': round(available_mb, 2),
        'status': status,
        'warning_threshold': warning_threshold * 100
    }


def should_warn_about_storage():
    """
    Check if we should warn administrators about storage.

    Returns:
        bool: True if storage is above warning threshold
    """
    stats = get_storage_stats()
    return stats['status'] in ('warning', 'critical')


def format_size_mb(size_mb):
    """
    Format size in MB to human-readable string.

    Args:
        size_mb (float): Size in megabytes

    Returns:
        str: Formatted size (e.g., "123.45 MB" or "1.23 GB")
    """
    if size_mb >= 1024:
        return f"{size_mb / 1024:.2f} GB"
    return f"{size_mb:.2f} MB"
