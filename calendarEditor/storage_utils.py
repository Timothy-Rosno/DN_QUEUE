"""
Database storage utilities for monitoring and managing database size.
"""
from django.db import connection
from django.conf import settings
from pathlib import Path
import os


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
