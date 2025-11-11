"""
Tests for userRegistration middleware.

Coverage:
- UserApprovalMiddleware: Approval checking, allowed URLs, staff bypass
"""
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User, AnonymousUser
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware

from userRegistration.models import UserProfile
from userRegistration.middleware import UserApprovalMiddleware


class UserApprovalMiddlewareTest(TestCase):
    """Test the UserApprovalMiddleware functionality."""

    def setUp(self):
        """Set up test data and middleware."""
        self.factory = RequestFactory()
        self.get_response = lambda request: HttpResponse()
        self.middleware = UserApprovalMiddleware(self.get_response)

        # Create users
        self.approved_user = User.objects.create_user(
            username='approved',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.approved_user, is_approved=True)

        self.unapproved_user = User.objects.create_user(
            username='unapproved',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.unapproved_user, is_approved=False)

        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )

        self.superuser = User.objects.create_user(
            username='superuser',
            password='testpass123',
            is_superuser=True
        )

    def _add_session_and_messages(self, request):
        """Helper to add session and messages to request."""
        SessionMiddleware(self.get_response).process_request(request)
        MessageMiddleware(self.get_response).process_request(request)
        request.session.save()

    def test_anonymous_user_allowed(self):
        """Test that anonymous users can access the site."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_approved_user_allowed(self):
        """Test that approved users can access protected pages."""
        request = self.factory.get('/schedule/my-queue/')
        request.user = self.approved_user
        self._add_session_and_messages(request)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_unapproved_user_blocked_from_protected_pages(self):
        """Test that unapproved users are blocked from protected pages."""
        request = self.factory.get('/schedule/my-queue/')
        request.user = self.unapproved_user
        self._add_session_and_messages(request)

        response = self.middleware(request)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

    def test_unapproved_user_can_access_login(self):
        """Test that unapproved users can access login page."""
        request = self.factory.get(reverse('login'))
        request.user = self.unapproved_user
        self._add_session_and_messages(request)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_unapproved_user_can_access_logout(self):
        """Test that unapproved users can access logout page."""
        request = self.factory.get(reverse('logout'))
        request.user = self.unapproved_user
        self._add_session_and_messages(request)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_unapproved_user_can_access_register(self):
        """Test that unapproved users can access registration page."""
        request = self.factory.get(reverse('register'))
        request.user = self.unapproved_user
        self._add_session_and_messages(request)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_staff_user_bypasses_approval_check(self):
        """Test that staff users bypass approval check."""
        request = self.factory.get('/schedule/my-queue/')
        request.user = self.staff_user
        self._add_session_and_messages(request)

        response = self.middleware(request)

        # Staff should be allowed regardless of approval status
        self.assertEqual(response.status_code, 200)

    def test_superuser_bypasses_approval_check(self):
        """Test that superusers bypass approval check."""
        request = self.factory.get('/schedule/my-queue/')
        request.user = self.superuser
        self._add_session_and_messages(request)

        response = self.middleware(request)

        # Superuser should be allowed regardless of approval status
        self.assertEqual(response.status_code, 200)

    def test_middleware_creates_profile_if_missing(self):
        """Test that middleware creates profile if user doesn't have one."""
        # Create user without profile
        user_no_profile = User.objects.create_user(
            username='noprofile',
            password='testpass123'
        )

        request = self.factory.get('/schedule/my-queue/')
        request.user = user_no_profile
        self._add_session_and_messages(request)

        # Profile should not exist yet
        self.assertFalse(hasattr(user_no_profile, 'profile'))

        response = self.middleware(request)

        # Middleware should create profile
        user_no_profile.refresh_from_db()
        self.assertTrue(UserProfile.objects.filter(user=user_no_profile).exists())

        # Profile should be unapproved
        profile = UserProfile.objects.get(user=user_no_profile)
        self.assertFalse(profile.is_approved)

        # Should be redirected since unapproved
        self.assertEqual(response.status_code, 302)

    def test_admin_urls_accessible_to_unapproved_users(self):
        """Test that unapproved users can access Django admin."""
        request = self.factory.get('/admin/')
        request.user = self.unapproved_user
        self._add_session_and_messages(request)

        response = self.middleware(request)

        # Should be allowed (actual admin permission check happens in Django admin)
        self.assertEqual(response.status_code, 200)


class UserApprovalMiddlewareIntegrationTest(TestCase):
    """Integration tests for UserApprovalMiddleware with full request/response cycle."""

    def setUp(self):
        """Set up test client and users."""
        self.client = Client()

        self.approved_user = User.objects.create_user(
            username='approved',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.approved_user, is_approved=True)

        self.unapproved_user = User.objects.create_user(
            username='unapproved',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.unapproved_user, is_approved=False)

    def test_approved_user_full_access(self):
        """Test that approved users have full access to the site."""
        self.client.login(username='approved', password='testpass123')

        # Should be able to access home page
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # Should be able to access protected pages
        response = self.client.get(reverse('my_queue'))
        self.assertEqual(response.status_code, 200)

    def test_unapproved_user_limited_access(self):
        """Test that unapproved users have limited access."""
        self.client.login(username='unapproved', password='testpass123')

        # Try to access protected page
        response = self.client.get(reverse('my_queue'), follow=True)

        # Should be redirected to login
        self.assertRedirects(response, reverse('login'))

        # Should see warning message
        messages = list(response.context['messages'])
        self.assertTrue(any('pending approval' in str(m).lower() for m in messages))

    def test_approval_workflow(self):
        """Test the complete approval workflow."""
        # Step 1: Unapproved user tries to access protected page
        self.client.login(username='unapproved', password='testpass123')
        response = self.client.get(reverse('my_queue'), follow=True)
        self.assertRedirects(response, reverse('login'))

        # Step 2: Admin approves user
        profile = self.unapproved_user.profile
        profile.is_approved = True
        profile.save()

        # Step 3: User can now access protected pages
        response = self.client.get(reverse('my_queue'))
        self.assertEqual(response.status_code, 200)

    def test_staff_full_access_without_approval(self):
        """Test that staff users have full access without approval."""
        staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
        # Create unapproved profile
        UserProfile.objects.create(user=staff_user, is_approved=False)

        self.client.login(username='staff', password='testpass123')

        # Should be able to access protected pages despite being unapproved
        response = self.client.get(reverse('my_queue'))
        self.assertEqual(response.status_code, 200)


class UserApprovalMiddlewareEdgeCasesTest(TestCase):
    """Test edge cases and error handling in UserApprovalMiddleware."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.get_response = lambda request: HttpResponse()
        self.middleware = UserApprovalMiddleware(self.get_response)

    def _add_session_and_messages(self, request):
        """Helper to add session and messages to request."""
        SessionMiddleware(self.get_response).process_request(request)
        MessageMiddleware(self.get_response).process_request(request)
        request.session.save()

    def test_user_without_profile_attribute(self):
        """Test handling of user without profile attribute."""
        user = User.objects.create_user(username='test', password='pass')
        # Explicitly ensure no profile exists
        UserProfile.objects.filter(user=user).delete()

        request = self.factory.get('/schedule/my-queue/')
        request.user = user
        self._add_session_and_messages(request)

        # Should handle gracefully and create profile
        response = self.middleware(request)

        # Profile should now exist
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_allowed_url_path_matching(self):
        """Test that allowed URLs are matched correctly with path prefixes."""
        user = User.objects.create_user(username='test', password='pass')
        UserProfile.objects.create(user=user, is_approved=False)

        # Test various admin URL paths
        admin_paths = [
            '/admin/',
            '/admin/auth/',
            '/admin/auth/user/',
            '/admin/auth/user/1/change/',
        ]

        for path in admin_paths:
            request = self.factory.get(path)
            request.user = user
            self._add_session_and_messages(request)

            response = self.middleware(request)

            # All admin paths should be allowed
            self.assertEqual(response.status_code, 200, f"Failed for path: {path}")
