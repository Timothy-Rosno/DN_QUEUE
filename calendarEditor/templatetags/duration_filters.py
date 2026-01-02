"""
Template filters for formatting durations.
"""
from django import template

register = template.Library()


@register.filter
def format_duration(hours):
    """
    Convert hours to "Nd Nh" format.

    Examples:
        25 hours -> "1d 1h"
        48 hours -> "2d 0h"
        10 hours -> "10h"
        0 hours -> "0h"
    """
    if hours is None:
        return "0h"

    hours = float(hours)
    days = int(hours // 24)
    remaining_hours = int(hours % 24)

    if days > 0:
        return f"{days}d {remaining_hours}h"
    else:
        return f"{remaining_hours}h"
