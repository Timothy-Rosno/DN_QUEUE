from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

class UserApprovalMiddleware:
    """Middleware to block unapproved users from accessing the site."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # List of URLs that unapproved users can access
        allowed_urls = [
            reverse('login'),
            reverse('logout'),
            reverse('register'),
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
                        messages.warning(request, 'Your account is pending approval. You will be notified once an administrator approves your account.')
                        return redirect('login')
            except Exception:
                # If no profile exists, create one
                from .models import UserProfile
                UserProfile.objects.create(user=request.user, is_approved=False)
                if not any(request.path.startswith(url) for url in allowed_urls):
                    messages.warning(request, 'Your account is pending approval. You will be notified once an administrator approves your account.')
                    return redirect('login')

        return self.get_response(request)
