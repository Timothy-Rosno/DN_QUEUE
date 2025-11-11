"""
Tests for calendarEditor admin views.

Coverage:
- Admin dashboard
- User management (approve, reject, delete)
- Machine management
- Queue management (reorder, reassign, queue next)
- Rush job review (approve, reject)
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from calendarEditor.models import Machine, QueueEntry
from userRegistration.models import UserProfile


class AdminDashboardViewTest(TestCase):
    """Test admin dashboard view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=False
        )

    def test_admin_dashboard_requires_staff(self):
        """Test that admin dashboard requires staff permissions."""
        # Not logged in
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

        # Regular user
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect (not authorized)

    def test_admin_dashboard_accessible_for_staff(self):
        """Test that admin dashboard is accessible for staff users."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'calendarEditor/admin/admin_dashboard.html')

    def test_admin_dashboard_shows_statistics(self):
        """Test that admin dashboard shows system statistics."""
        self.client.login(username='admin', password='testpass123')

        # Create some test data
        machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

        QueueEntry.objects.create(
            user=self.regular_user,
            title='Test Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=machine,
            status='queued'
        )

        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Should show machine and queue statistics
        self.assertContains(response, 'Test Fridge')


class AdminUsersViewTest(TestCase):
    """Test admin user management views."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True
        )

        self.pending_user = User.objects.create_user(
            username='pending',
            password='testpass123'
        )
        self.pending_profile = UserProfile.objects.create(
            user=self.pending_user,
            is_approved=False,
            full_name='Pending User',
            affiliation='Test University'
        )

    def test_admin_users_requires_staff(self):
        """Test that admin users view requires staff permissions."""
        response = self.client.get(reverse('admin_users'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_admin_users_accessible_for_staff(self):
        """Test that admin users view is accessible for staff."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_users'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'calendarEditor/admin/admin_users.html')

    def test_admin_users_shows_pending_users(self):
        """Test that admin users view shows pending users."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_users'))
        self.assertContains(response, 'pending')
        self.assertContains(response, 'Pending User')

    def test_approve_user(self):
        """Test approving a pending user."""
        self.client.login(username='admin', password='testpass123')

        response = self.client.post(
            reverse('approve_user', args=[self.pending_user.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after approval

        self.pending_profile.refresh_from_db()
        self.assertTrue(self.pending_profile.is_approved)

    def test_reject_user(self):
        """Test rejecting a pending user."""
        self.client.login(username='admin', password='testpass123')

        response = self.client.post(
            reverse('reject_user', args=[self.pending_user.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after rejection

        # User should be deleted
        self.assertFalse(User.objects.filter(id=self.pending_user.id).exists())

    def test_delete_user(self):
        """Test deleting a user."""
        self.client.login(username='admin', password='testpass123')

        response = self.client.post(
            reverse('delete_user', args=[self.pending_user.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after deletion

        # User should be deleted
        self.assertFalse(User.objects.filter(id=self.pending_user.id).exists())


class AdminMachinesViewTest(TestCase):
    """Test admin machine management view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True
        )

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            b_field_x=2.0,
            dc_lines=12,
            cooldown_hours=8,
            current_status='idle'
        )

    def test_admin_machines_requires_staff(self):
        """Test that admin machines view requires staff permissions."""
        response = self.client.get(reverse('admin_machines'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_admin_machines_accessible_for_staff(self):
        """Test that admin machines view is accessible for staff."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_machines'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'calendarEditor/admin/admin_machines.html')

    def test_admin_machines_shows_all_machines(self):
        """Test that admin machines view shows all machines."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_machines'))
        self.assertContains(response, 'Test Fridge')


class AdminQueueViewTest(TestCase):
    """Test admin queue management view and actions."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8,
            current_status='idle'
        )

        self.entry1 = QueueEntry.objects.create(
            user=self.user,
            title='Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=1
        )

        self.entry2 = QueueEntry.objects.create(
            user=self.user,
            title='Job 2',
            required_min_temp=0.1,
            estimated_duration_hours=3.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=2
        )

    def test_admin_queue_requires_staff(self):
        """Test that admin queue view requires staff permissions."""
        response = self.client.get(reverse('admin_queue'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_admin_queue_accessible_for_staff(self):
        """Test that admin queue view is accessible for staff."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_queue'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'calendarEditor/admin/admin_queue.html')

    def test_admin_queue_shows_all_entries(self):
        """Test that admin queue view shows all queue entries."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_queue'))
        self.assertContains(response, 'Job 1')
        self.assertContains(response, 'Job 2')

    def test_move_queue_up(self):
        """Test moving a queue entry up in position."""
        self.client.login(username='admin', password='testpass123')

        # Move entry2 up (should swap with entry1)
        response = self.client.post(
            reverse('move_queue_up', args=[self.entry2.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after move

        self.entry1.refresh_from_db()
        self.entry2.refresh_from_db()

        # Positions should be swapped
        self.assertEqual(self.entry2.queue_position, 1)
        self.assertEqual(self.entry1.queue_position, 2)

    def test_move_queue_down(self):
        """Test moving a queue entry down in position."""
        self.client.login(username='admin', password='testpass123')

        # Move entry1 down (should swap with entry2)
        response = self.client.post(
            reverse('move_queue_down', args=[self.entry1.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after move

        self.entry1.refresh_from_db()
        self.entry2.refresh_from_db()

        # Positions should be swapped
        self.assertEqual(self.entry1.queue_position, 2)
        self.assertEqual(self.entry2.queue_position, 1)

    def test_queue_next(self):
        """Test queuing next entry (starting a job)."""
        self.client.login(username='admin', password='testpass123')

        response = self.client.post(
            reverse('queue_next', args=[self.entry1.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after action

        self.entry1.refresh_from_db()
        # Entry should be marked as running
        self.assertEqual(self.entry1.status, 'running')
        self.assertIsNotNone(self.entry1.started_at)

    def test_reassign_machine(self):
        """Test reassigning a queue entry to a different machine."""
        self.client.login(username='admin', password='testpass123')

        # Create another machine
        machine2 = Machine.objects.create(
            name='Fridge 2',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=6
        )

        response = self.client.post(
            reverse('reassign_machine', args=[self.entry1.id]),
            {'machine_id': machine2.id}
        )
        self.assertEqual(response.status_code, 302)  # Redirect after reassignment

        self.entry1.refresh_from_db()
        self.assertEqual(self.entry1.assigned_machine, machine2)


class AdminRushJobsViewTest(TestCase):
    """Test admin rush job review functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

        self.rush_entry = QueueEntry.objects.create(
            user=self.user,
            title='Urgent Job',
            required_min_temp=0.1,
            estimated_duration_hours=1.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=5,
            is_rush_job=True,
            rush_job_submitted_at=timezone.now(),
            special_requirements='Need this ASAP for paper deadline'
        )

    def test_admin_rush_jobs_requires_staff(self):
        """Test that rush jobs view requires staff permissions."""
        response = self.client.get(reverse('admin_rush_jobs'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_admin_rush_jobs_accessible_for_staff(self):
        """Test that rush jobs view is accessible for staff."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_rush_jobs'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'calendarEditor/admin/admin_rush_jobs.html')

    def test_admin_rush_jobs_shows_rush_requests(self):
        """Test that rush jobs view shows all rush job requests."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('admin_rush_jobs'))
        self.assertContains(response, 'Urgent Job')
        self.assertContains(response, 'Need this ASAP')

    def test_approve_rush_job(self):
        """Test approving a rush job request."""
        self.client.login(username='admin', password='testpass123')

        response = self.client.post(
            reverse('approve_rush_job', args=[self.rush_entry.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after approval

        self.rush_entry.refresh_from_db()
        # Entry should be moved to position 1 (or given high priority)
        self.assertEqual(self.rush_entry.queue_position, 1)

    def test_reject_rush_job(self):
        """Test rejecting a rush job request."""
        self.client.login(username='admin', password='testpass123')

        original_position = self.rush_entry.queue_position

        response = self.client.post(
            reverse('reject_rush_job', args=[self.rush_entry.id])
        )
        self.assertEqual(response.status_code, 302)  # Redirect after rejection

        self.rush_entry.refresh_from_db()
        # is_rush_job flag should be cleared
        self.assertFalse(self.rush_entry.is_rush_job)
        # Position should remain unchanged
        self.assertEqual(self.rush_entry.queue_position, original_position)


class AdminPermissionsTest(TestCase):
    """Test that admin views properly enforce permissions."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=False
        )

    def test_regular_user_cannot_access_admin_views(self):
        """Test that regular users cannot access any admin views."""
        self.client.login(username='regular', password='testpass123')

        admin_urls = [
            reverse('admin_dashboard'),
            reverse('admin_users'),
            reverse('admin_machines'),
            reverse('admin_queue'),
            reverse('admin_rush_jobs'),
        ]

        for url in admin_urls:
            response = self.client.get(url)
            # Should redirect or return 403
            self.assertNotEqual(response.status_code, 200)
