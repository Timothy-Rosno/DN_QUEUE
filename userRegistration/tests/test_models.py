"""
Tests for userRegistration models.

Coverage:
- UserProfile: Creation, relationships, approval status
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from userRegistration.models import UserProfile


class UserProfileModelTest(TestCase):
    """Test UserProfile model functionality."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_user_profile_creation(self):
        """Test creating a user profile."""
        profile = UserProfile.objects.create(
            user=self.user,
            phone_number='123-456-7890',
            department='Physics',
            notes='Test user profile',
            is_approved=False
        )

        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.phone_number, '123-456-7890')
        self.assertEqual(profile.department, 'Physics')
        self.assertFalse(profile.is_approved)

    def test_user_profile_string_representation(self):
        """Test __str__ method."""
        profile = UserProfile.objects.create(user=self.user)

        expected = "testuser's Profile"
        self.assertEqual(str(profile), expected)

    def test_user_profile_defaults(self):
        """Test that profile has correct default values."""
        profile = UserProfile.objects.create(user=self.user)

        self.assertEqual(profile.phone_number, '')
        self.assertEqual(profile.department, '')
        self.assertEqual(profile.notes, '')
        self.assertFalse(profile.is_approved)
        self.assertIsNone(profile.approved_by)
        self.assertIsNone(profile.approved_at)

    def test_user_profile_approval(self):
        """Test approving a user profile."""
        admin = User.objects.create_user(
            username='admin',
            password='adminpass',
            is_staff=True
        )

        profile = UserProfile.objects.create(
            user=self.user,
            is_approved=False
        )

        # Approve the profile
        approval_time = timezone.now()
        profile.is_approved = True
        profile.approved_by = admin
        profile.approved_at = approval_time
        profile.save()

        profile.refresh_from_db()

        self.assertTrue(profile.is_approved)
        self.assertEqual(profile.approved_by, admin)
        self.assertEqual(profile.approved_at, approval_time)

    def test_user_profile_one_to_one_relationship(self):
        """Test that UserProfile has one-to-one relationship with User."""
        profile = UserProfile.objects.create(user=self.user)

        # Should be able to access profile from user
        self.assertEqual(self.user.profile, profile)

        # Should only be able to create one profile per user
        with self.assertRaises(Exception):
            UserProfile.objects.create(user=self.user)

    def test_user_profile_cascade_delete(self):
        """Test that profile is deleted when user is deleted."""
        profile = UserProfile.objects.create(user=self.user)
        profile_id = profile.id

        # Delete the user
        self.user.delete()

        # Profile should also be deleted
        self.assertFalse(UserProfile.objects.filter(id=profile_id).exists())

    def test_user_profile_approved_by_relationship(self):
        """Test the approved_by foreign key relationship."""
        admin = User.objects.create_user(username='admin', password='pass', is_staff=True)
        profile = UserProfile.objects.create(
            user=self.user,
            approved_by=admin,
            is_approved=True
        )

        # Should be able to access approved users from admin
        approved_profiles = admin.approved_users.all()
        self.assertIn(profile, approved_profiles)

    def test_user_profile_approved_by_set_null_on_delete(self):
        """Test that approved_by is set to NULL when approver is deleted."""
        admin = User.objects.create_user(username='admin', password='pass', is_staff=True)
        profile = UserProfile.objects.create(
            user=self.user,
            approved_by=admin,
            is_approved=True
        )

        # Delete the admin
        admin.delete()

        profile.refresh_from_db()
        # Profile should still exist, but approved_by should be None
        self.assertIsNone(profile.approved_by)
        self.assertTrue(profile.is_approved)  # Approval status remains

    def test_user_profile_timestamps(self):
        """Test that created_at and updated_at work correctly."""
        profile = UserProfile.objects.create(user=self.user)

        self.assertIsNotNone(profile.created_at)
        self.assertIsNotNone(profile.updated_at)

        original_updated = profile.updated_at

        # Update profile
        profile.department = 'Chemistry'
        profile.save()

        profile.refresh_from_db()
        # updated_at should change
        self.assertGreater(profile.updated_at, original_updated)

        # created_at should not change
        self.assertEqual(profile.created_at, profile.created_at)

    def test_user_profile_optional_fields(self):
        """Test that optional fields can be blank."""
        profile = UserProfile.objects.create(
            user=self.user
            # All optional fields left blank
        )

        self.assertEqual(profile.phone_number, '')
        self.assertEqual(profile.department, '')
        self.assertEqual(profile.notes, '')

        # Should save without errors
        profile.save()
