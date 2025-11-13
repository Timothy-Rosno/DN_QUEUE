from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.urls import reverse

class UserApprovalMiddleware:
    """Middleware to block unapproved users from accessing the site."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip middleware for health check endpoint to avoid DB queries during cold starts
        if request.path == '/schedule/health/':
            return self.get_response(request)

        # List of URLs that unapproved users can access
        allowed_urls = [
            reverse('login'),
            reverse('logout'),
            reverse('register'),
            reverse('home'),  # Allow home page access
            '/admin/',  # Allow access to Django admin
        ]

        # Check if user is authenticated
        if request.user.is_authenticated:
            # Staff users and superusers bypass approval check
            if request.user.is_staff or request.user.is_superuser:
                return self.get_response(request)

            # Check if user has a profile and is approved
            try:
                profile = request.user.profile
                if not profile.is_approved:
                    # Allow access to allowed URLs
                    if not any(request.path.startswith(url) for url in allowed_urls):
                        # Log out the user and redirect to home
                        logout(request)
                        messages.warning(request, 'Your account is pending approval by an administrator. You will be able to log in once your account is approved.')
                        return redirect('home')
            except Exception:
                # If no profile exists, create one
                from .models import UserProfile
                UserProfile.objects.create(user=request.user, is_approved=False)
                if not any(request.path.startswith(url) for url in allowed_urls):
                    # Log out the user and redirect to home
                    logout(request)
                    messages.warning(request, 'Your account is pending approval by an administrator. You will be able to log in once your account is approved.')
                    return redirect('home')

        return self.get_response(request)
