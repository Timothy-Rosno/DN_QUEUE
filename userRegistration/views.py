from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from .forms import UserRegistrationForm, UserProfileForm, NotificationPreferenceForm
from .models import UserProfile
from calendarEditor.models import NotificationPreference


class CustomLoginView(LoginView):
    """
    Custom login view that redirects based on user type:
    - Admin/staff users → admin dashboard
    - Regular users → home page

    Also handles marking one-time login tokens as used after successful login.
    """

    def form_valid(self, form):
        """Handle successful login with optional 'Remember Me' functionality."""
        from django.contrib.auth import logout
        from django.contrib import messages
        from django.shortcuts import redirect

        # Check if user selected "Remember Me" checkbox
        remember_me = self.request.POST.get('remember_me', False)

        # Call parent form_valid to log the user in
        response = super().form_valid(form)

        # Capture device info at login
        user = self.request.user
        try:
            profile = user.profile

            # Extract IP address
            x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = self.request.META.get('REMOTE_ADDR', '')

            # Parse user agent
            user_agent = self.request.META.get('HTTP_USER_AGENT', '').lower()

            # Detect browser
            browser = 'Unknown'
            if 'chrome' in user_agent and 'edg' not in user_agent:
                browser = 'Chrome'
            elif 'firefox' in user_agent:
                browser = 'Firefox'
            elif 'safari' in user_agent and 'chrome' not in user_agent:
                browser = 'Safari'
            elif 'edg' in user_agent:
                browser = 'Edge'

            # Detect OS
            os_name = 'Unknown'
            if 'windows' in user_agent:
                os_name = 'Windows'
            elif 'mac' in user_agent:
                os_name = 'macOS'
            elif 'linux' in user_agent:
                os_name = 'Linux'
            elif 'android' in user_agent:
                os_name = 'Android'
            elif 'iphone' in user_agent or 'ipad' in user_agent:
                os_name = 'iOS'

            # Detect device type
            device = 'Desktop'
            if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
                device = 'Mobile'
            elif 'ipad' in user_agent or 'tablet' in user_agent:
                device = 'Tablet'

            # Update profile
            profile.last_login_ip = ip_address
            profile.last_login_browser = browser
            profile.last_login_os = os_name
            profile.last_login_device = device
            profile.save(update_fields=['last_login_ip', 'last_login_browser', 'last_login_os', 'last_login_device'])
        except Exception as e:
            # Don't break login if tracking fails
            print(f"[LoginTracking] Error: {e}")
            pass

        # Check if user is approved (skip for staff/superusers)
        if not (user.is_staff or user.is_superuser):
            try:
                profile = user.profile
                if not profile.is_approved:
                    # Log out the user immediately
                    logout(self.request)
                    messages.warning(self.request, 'Your account is pending approval by an administrator. You will be able to log in once your account is approved.')
                    return redirect('login')
            except Exception:
                # If no profile exists, create one and log them out
                from .models import UserProfile
                UserProfile.objects.create(user=user, is_approved=False)
                logout(self.request)
                messages.warning(self.request, 'Your account is pending approval by an administrator. You will be able to log in once your account is approved.')
                return redirect('login')

        # Set session expiry based on "Remember Me" preference
        if remember_me:
            # Long session: 1 year (for personal devices)
            self.request.session.set_expiry(31536000)  # 365 days in seconds
            # Store flag to disable auto-logout for "Remember Me" users
            self.request.session['remember_me'] = True
        else:
            # Shorter session: 7 days (safer for potentially shared devices)
            self.request.session.set_expiry(604800)  # 7 days in seconds
            # Enable auto-logout for non-"Remember Me" users
            self.request.session['remember_me'] = False

        # Tokens are reusable, so no need to mark as used
        # The get_success_url will handle redirection
        return response

    def get_success_url(self):
        """Determine redirect URL based on user type or session 'next' parameter."""
        user = self.request.user

        # FIRST: Check if there's a pending token from notification link
        pending_token = self.request.session.get('pending_token')
        token_auth_hint = self.request.session.get('token_auth_hint')

        if pending_token and token_auth_hint:
            # Clean up session
            del self.request.session['pending_token']
            if 'token_auth_hint' in self.request.session:
                del self.request.session['token_auth_hint']

            # Check if user logged in as the correct user
            if user.username == token_auth_hint:
                # Correct user! Redirect to token_login which will redirect to the intended page
                return reverse('token_login', kwargs={'token': pending_token})
            else:
                # Wrong user logged in! Redirect to home with warning
                messages.warning(self.request, 'This notification is not for your account. Returning to home page.')
                return reverse('home')

        # Second priority: Check Django's standard redirect_url handling (from GET/POST 'next' parameter)
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url

        # Third priority: Check if there's a redirect URL from session (notification link)
        next_url = self.request.session.get('next')
        if next_url:
            # Clean up session
            if 'next' in self.request.session:
                del self.request.session['next']
            return next_url

        # Admin and staff users go to admin dashboard
        if user.is_staff or user.is_superuser:
            return reverse('admin_dashboard')

        # Regular approved users go to home page
        return reverse('home')


def register(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        profile_form = UserProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            # Staff users don't require approval
            profile.is_approved = user.is_staff or user.is_superuser

            # Hash and save security answer
            security_answer = profile_form.cleaned_data.get('security_answer')
            if security_answer:
                profile.set_security_answer(security_answer)

            profile.save()

            username = user_form.cleaned_data.get('username')

            # Notify admins about new user signup
            from calendarEditor import notifications
            notifications.notify_admins_new_user(user)

            messages.success(request, f'Account created successfully! Your account is pending approval by an administrator. You will be able to log in once approved.')
            return redirect('login')
    else:
        user_form = UserRegistrationForm()
        profile_form = UserProfileForm()

    return render(request, 'userRegistration/register.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

@login_required
def profile(request):
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        # Create profile, auto-approve staff users
        user_profile = UserProfile.objects.create(
            user=request.user,
            is_approved=request.user.is_staff or request.user.is_superuser
        )

    # Get or create notification preferences
    notification_prefs = NotificationPreference.get_or_create_for_user(request.user)

    if request.method == 'POST':
        # Determine which form was submitted
        if 'submit_profile' in request.POST:
            form = UserProfileForm(request.POST, instance=user_profile)
            notification_form = NotificationPreferenceForm(instance=notification_prefs, user=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
        elif 'submit_notifications' in request.POST:
            form = UserProfileForm(instance=user_profile)
            notification_form = NotificationPreferenceForm(request.POST, instance=notification_prefs, user=request.user)
            if notification_form.is_valid():
                # Save without committing to ensure critical notifications stay True
                prefs = notification_form.save(commit=False)
                prefs.notify_on_deck = True
                prefs.notify_ready_for_check_in = True
                prefs.notify_checkout_reminder = True

                # Force admin notifications to remain True if user is staff
                if request.user.is_staff or request.user.is_superuser:
                    prefs.notify_admin_new_user = True
                    prefs.notify_admin_rush_job = True

                prefs.save()
                messages.success(request, 'Notification preferences updated successfully!')
                return redirect('profile')
            else:
                # Log validation errors
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Notification form validation failed: {notification_form.errors}')
                messages.error(request, 'Failed to save notification preferences. Please check the form for errors.')
        else:
            form = UserProfileForm(instance=user_profile)
            notification_form = NotificationPreferenceForm(instance=notification_prefs, user=request.user)
    else:
        form = UserProfileForm(instance=user_profile)
        notification_form = NotificationPreferenceForm(instance=notification_prefs, user=request.user)

    # Get followed presets for display
    followed_presets = notification_prefs.followed_presets.all().order_by('display_name')

    return render(request, 'userRegistration/profile.html', {
        'form': form,
        'notification_form': notification_form,
        'user_profile': user_profile,
        'followed_presets': followed_presets,
    })


def forgot_password(request):
    """Step 1: User enters username to initiate password reset."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()

        try:
            user = User.objects.get(username=username)
            # Check if user has a security question set up
            if hasattr(user, 'profile') and user.profile.security_question:
                # Store username in session and redirect to security question page
                request.session['reset_username'] = username
                return redirect('security_question')
            else:
                messages.error(request, 'This account does not have a security question set up. Please contact an administrator.')
        except User.DoesNotExist:
            messages.error(request, 'Username not found.')

    return render(request, 'userRegistration/forgot_password.html')


def security_question(request):
    """Step 2: Display security question and verify answer."""
    # Get username from session
    username = request.session.get('reset_username')
    if not username:
        messages.error(request, 'Please start the password reset process again.')
        return redirect('forgot_password')

    try:
        user = User.objects.get(username=username)
        profile = user.profile

        if request.method == 'POST':
            answer = request.POST.get('security_answer', '').strip()

            if profile.check_security_answer(answer):
                # Correct answer - allow password reset
                request.session['reset_verified'] = True
                return redirect('reset_password')
            else:
                messages.error(request, 'Incorrect answer. Please try again.')

        # Get the security question text (handles both predefined and custom questions)
        security_question_text = profile.get_security_question_text()

        return render(request, 'userRegistration/security_question.html', {
            'username': username,
            'security_question': security_question_text
        })

    except (User.DoesNotExist, AttributeError):
        messages.error(request, 'Invalid password reset session. Please start again.')
        return redirect('forgot_password')


def reset_password(request):
    """Step 3: User sets new password after answering security question."""
    # Verify that user has completed security question step
    if not request.session.get('reset_verified'):
        messages.error(request, 'Please complete the security question first.')
        return redirect('forgot_password')

    username = request.session.get('reset_username')
    if not username:
        messages.error(request, 'Please start the password reset process again.')
        return redirect('forgot_password')

    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
        elif len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        else:
            try:
                user = User.objects.get(username=username)
                user.set_password(password1)
                user.save()

                # Clear session data
                request.session.pop('reset_username', None)
                request.session.pop('reset_verified', None)

                messages.success(request, 'Password reset successfully! You can now log in with your new password.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
                return redirect('forgot_password')

    return render(request, 'userRegistration/reset_password.html', {
        'username': username
    })


def recover_username(request):
    """Recover username by entering email address."""
    found_usernames = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        # Handle multiple users with same email
        users = User.objects.filter(email=email)

        if users.exists():
            found_usernames = [user.username for user in users]
        else:
            messages.error(request, 'No account found with that email address.')

    return render(request, 'userRegistration/recover_username.html', {
        'found_usernames': found_usernames
    })


@login_required
def change_security_question(request):
    """Allow users to change their security question after verifying current answer."""
    from .forms import ChangeSecurityQuestionForm

    # Check if user has a security question set
    if not request.user.profile.security_question:
        messages.error(request, 'You do not have a security question set. Please contact an administrator.')
        return redirect('profile')

    if request.method == 'POST':
        form = ChangeSecurityQuestionForm(request.user, request.POST)
        if form.is_valid():
            # Update security question and answer
            profile = request.user.profile
            profile.security_question = form.cleaned_data['new_security_question']

            if form.cleaned_data['new_security_question'] == 'custom':
                profile.security_question_custom = form.cleaned_data['new_security_question_custom']

            profile.set_security_answer(form.cleaned_data['new_security_answer'])
            profile.save()

            messages.success(request, 'Security question updated successfully!')
            return redirect('profile')
    else:
        form = ChangeSecurityQuestionForm(request.user)

    return render(request, 'userRegistration/change_security_question.html', {
        'form': form
    })
