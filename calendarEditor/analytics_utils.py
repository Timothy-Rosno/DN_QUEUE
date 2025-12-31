"""
Utilities for efficient analytics tracking using Redis/cache.
"""
from django.core.cache import cache
from datetime import datetime, timedelta


def increment_counter(key, amount=1, timeout=86400):
    """Increment a counter in cache (Redis-safe)."""
    try:
        # Try to increment (works with Redis)
        current = cache.get(key, 0)
        cache.set(key, current + amount, timeout)
        return current + amount
    except Exception:
        return None


def add_to_set(key, value, timeout=86400):
    """Add value to a set in cache (simulated with list for non-Redis backends)."""
    try:
        current_set = cache.get(key, set())
        if not isinstance(current_set, set):
            current_set = set(current_set) if current_set else set()
        current_set.add(value)
        cache.set(key, current_set, timeout)
        return len(current_set)
    except Exception:
        return None


def get_set_size(key):
    """Get size of a set in cache."""
    try:
        current_set = cache.get(key, set())
        if isinstance(current_set, set):
            return len(current_set)
        elif isinstance(current_set, (list, tuple)):
            return len(set(current_set))
        return 0
    except Exception:
        return 0


def add_to_sorted_set(key, member, score, timeout=900):
    """
    Add to sorted set (Redis sorted set simulation).
    For users online tracking.
    """
    try:
        sorted_set = cache.get(key, {})
        if not isinstance(sorted_set, dict):
            sorted_set = {}

        # Remove old entries (older than timeout)
        now = datetime.now().timestamp()
        cutoff = now - timeout
        sorted_set = {k: v for k, v in sorted_set.items() if v >= cutoff}

        # Add new entry
        sorted_set[member] = score
        cache.set(key, sorted_set, timeout)
        return len(sorted_set)
    except Exception:
        return None


def get_sorted_set_count(key, min_score=None):
    """Get count of members in sorted set above min_score."""
    try:
        sorted_set = cache.get(key, {})
        if not isinstance(sorted_set, dict):
            return 0

        if min_score is not None:
            return sum(1 for score in sorted_set.values() if score >= min_score)
        return len(sorted_set)
    except Exception:
        return 0
