"""
Custom decorators for calendarEditor views.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def developer_required(view_func):
    """
    Decorator to require developer role access.

    Checks if the user is a developer or superuser.
    Redirects to home with error message if not authorized.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Check if user has profile
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'Developer access required.')
            return redirect('home')

        # Check if user is developer or superuser
        if not (request.user.profile.is_developer or request.user.is_superuser):
            messages.error(request, 'Developer access required.')
            return redirect('home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view
