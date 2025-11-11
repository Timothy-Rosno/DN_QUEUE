"""
Tests for calendarEditor views.

Coverage:
- Public display views: home page, machine status
- Queue management: submit, my_queue, cancel
- Preset views: create, edit, copy, delete, load
- Notification API: list, mark read, mark all read
- Legacy views: schedule list, create, edit, delete
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from calendarEditor.models import (
    Machine, QueueEntry, QueuePreset, Notification, NotificationPreference
)


class HomeViewTest(TestCase):
    """Test the public home page view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        self.machine1 = Machine.objects.create(
            name='Fridge 1',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8,
            current_status='idle',
            is_available=True
        )

        self.machine2 = Machine.objects.create(
            name='Fridge 2',
            min_temp=0.05,
            max_temp=300,
            cooldown_hours=6,
            current_status='running',
            is_available=False
        )

        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_home_page_accessible(self):
        """Test that home page is accessible without authentication."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'calendarEditor/public/home.html')

    def test_home_page_shows_machines(self):
        """Test that home page displays all machines."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Fridge 1')
        self.assertContains(response, 'Fridge 2')

    def test_home_page_shows_machine_status(self):
        """Test that machine statuses are displayed."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Idle')
        self.assertContains(response, 'Running')

    def test_home_page_shows_queue_data(self):
        """Test that queue information is displayed."""
        # Create queue entries
        QueueEntry.objects.create(
            user=self.user,
            title='Test Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine1,
            status='queued',
            queue_position=1
        )

        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        # Queue count should be visible
        self.assertContains(response, 'Test Job 1')


class SubmitQueueEntryViewTest(TestCase):
    """Test queue entry submission view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            b_field_x=2.0,
            b_field_y=2.0,
            b_field_z=10.0,
            dc_lines=12,
            rf_lines=2,
            cooldown_hours=8,
            current_status='idle',
            is_available=True
        )

    def test_submit_view_requires_login(self):
        """Test that submit view requires authentication."""
        response = self.client.get(reverse('submit_queue'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_submit_view_get(self):
        """Test GET request to submit view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('submit_queue'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'calendarEditor/submit_queue.html')

    def test_submit_queue_entry_valid(self):
        """Test submitting a valid queue entry."""
        self.client.login(username='testuser', password='testpass123')

        data = {
            'title': 'Test Experiment',
            'description': 'Testing submission',
            'required_min_temp': '0.1',
            'required_max_temp': '10.0',
            'required_b_field_x': '0.5',
            'required_b_field_y': '0.0',
            'required_b_field_z': '0.0',
            'required_b_field_direction': '',
            'required_dc_lines': '6',
            'required_rf_lines': '1',
            'required_daughterboard': '',
            'requires_optical': False,
            'estimated_duration_hours': '3.0',
            'special_requirements': ''
        }

        response = self.client.post(reverse('submit_queue'), data)

        # Should redirect after successful submission
        self.assertEqual(response.status_code, 302)

        # Check that entry was created
        self.assertEqual(QueueEntry.objects.count(), 1)
        entry = QueueEntry.objects.first()
        self.assertEqual(entry.title, 'Test Experiment')
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.status, 'queued')

    def test_submit_queue_entry_invalid_missing_required(self):
        """Test submitting queue entry with missing required fields."""
        self.client.login(username='testuser', password='testpass123')

        data = {
            'title': 'Test Experiment',
            # Missing required_min_temp and estimated_duration_hours
        }

        response = self.client.post(reverse('submit_queue'), data)

        # Should return form with errors
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'required_min_temp', 'This field is required.')


class MyQueueViewTest(TestCase):
    """Test my queue view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.other_user = User.objects.create_user(username='otheruser', password='testpass123')

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

    def test_my_queue_requires_login(self):
        """Test that my_queue view requires authentication."""
        response = self.client.get(reverse('my_queue'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_my_queue_shows_user_entries_only(self):
        """Test that my_queue only shows current user's entries."""
        self.client.login(username='testuser', password='testpass123')

        # Create entry for current user
        QueueEntry.objects.create(
            user=self.user,
            title='My Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued'
        )

        # Create entry for other user
        QueueEntry.objects.create(
            user=self.other_user,
            title='Other Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued'
        )

        response = self.client.get(reverse('my_queue'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Job')
        self.assertNotContains(response, 'Other Job')

    def test_my_queue_shows_all_statuses(self):
        """Test that my_queue shows queued, running, and completed entries."""
        self.client.login(username='testuser', password='testpass123')

        QueueEntry.objects.create(
            user=self.user,
            title='Queued Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            status='queued'
        )

        QueueEntry.objects.create(
            user=self.user,
            title='Running Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            status='running'
        )

        QueueEntry.objects.create(
            user=self.user,
            title='Completed Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            status='completed'
        )

        response = self.client.get(reverse('my_queue'))
        self.assertContains(response, 'Queued Job')
        self.assertContains(response, 'Running Job')
        self.assertContains(response, 'Completed Job')


class CancelQueueEntryViewTest(TestCase):
    """Test queue entry cancellation."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.other_user = User.objects.create_user(username='otheruser', password='testpass123')

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

        self.entry = QueueEntry.objects.create(
            user=self.user,
            title='Test Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=1
        )

    def test_cancel_requires_login(self):
        """Test that cancel view requires authentication."""
        response = self.client.post(reverse('cancel_queue', args=[self.entry.pk]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_cancel_own_entry(self):
        """Test that users can cancel their own entries."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('cancel_queue', args=[self.entry.pk]))
        self.assertEqual(response.status_code, 302)  # Redirect after cancel

        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, 'cancelled')

    def test_cannot_cancel_other_user_entry(self):
        """Test that users cannot cancel other users' entries."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.post(reverse('cancel_queue', args=[self.entry.pk]))
        # Should be forbidden or redirect
        self.assertIn(response.status_code, [302, 403, 404])

        self.entry.refresh_from_db()
        # Entry should NOT be cancelled
        self.assertEqual(self.entry.status, 'queued')


class PresetViewsTest(TestCase):
    """Test preset-related views."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.other_user = User.objects.create_user(username='otheruser', password='testpass123')

        self.preset = QueuePreset.objects.create(
            name='Test Preset',
            creator=self.user,
            required_min_temp=0.1,
            required_dc_lines=6,
            estimated_duration_hours=2.0,
            is_public=False
        )

    def test_create_preset_requires_login(self):
        """Test that create preset requires authentication."""
        response = self.client.get(reverse('create_preset'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_create_preset_get(self):
        """Test GET request to create preset view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('create_preset'))
        self.assertEqual(response.status_code, 200)

    def test_create_preset_post_valid(self):
        """Test creating a new preset with valid data."""
        self.client.login(username='testuser', password='testpass123')

        data = {
            'name': 'New Preset',
            'required_min_temp': '0.05',
            'required_dc_lines': '8',
            'estimated_duration_hours': '3.0',
            'is_public': False
        }

        response = self.client.post(reverse('create_preset'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after creation

        # Check that preset was created
        self.assertEqual(QueuePreset.objects.count(), 2)
        new_preset = QueuePreset.objects.get(name='New Preset')
        self.assertEqual(new_preset.creator, self.user)

    def test_edit_preset_own_preset(self):
        """Test editing own preset."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('edit_preset', args=[self.preset.id]))
        self.assertEqual(response.status_code, 200)

    def test_edit_preset_other_user_preset(self):
        """Test that users cannot edit other users' private presets."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.get(reverse('edit_preset', args=[self.preset.id]))
        # Should be forbidden or redirect
        self.assertIn(response.status_code, [302, 403, 404])

    def test_copy_preset(self):
        """Test copying a preset."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('copy_preset', args=[self.preset.id]))
        self.assertEqual(response.status_code, 302)  # Redirect after copy

        # Should have 2 presets now
        self.assertEqual(QueuePreset.objects.count(), 2)
        copied = QueuePreset.objects.exclude(id=self.preset.id).first()
        self.assertIn('Copy', copied.name)

    def test_delete_preset_own_preset(self):
        """Test deleting own preset."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('delete_preset', args=[self.preset.id]))
        self.assertEqual(response.status_code, 302)  # Redirect after delete

        self.assertEqual(QueuePreset.objects.count(), 0)

    def test_delete_preset_other_user_preset(self):
        """Test that users cannot delete other users' presets."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.post(reverse('delete_preset', args=[self.preset.id]))
        # Should be forbidden or redirect
        self.assertIn(response.status_code, [302, 403, 404])

        # Preset should still exist
        self.assertEqual(QueuePreset.objects.count(), 1)

    def test_load_preset_ajax(self):
        """Test loading preset data via AJAX."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('load_preset', args=[self.preset.id]))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['preset']['name'], 'Test Preset')
        self.assertEqual(float(data['preset']['required_min_temp']), 0.1)


class NotificationAPIViewsTest(TestCase):
    """Test notification API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Create some notifications
        self.notif1 = Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='Job Started',
            message='Your job has started.',
            is_read=False
        )

        self.notif2 = Notification.objects.create(
            recipient=self.user,
            notification_type='job_completed',
            title='Job Completed',
            message='Your job has completed.',
            is_read=True
        )

    def test_notification_list_api_requires_login(self):
        """Test that notification list API requires authentication."""
        response = self.client.get(reverse('notification_list_api'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_notification_list_api(self):
        """Test fetching notification list via API."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('notification_list_api'))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['notifications']), 2)
        self.assertEqual(data['unread_count'], 1)

    def test_notification_mark_read_api(self):
        """Test marking a notification as read via API."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('notification_mark_read_api'),
            json.dumps({'notification_id': self.notif1.id}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        self.notif1.refresh_from_db()
        self.assertTrue(self.notif1.is_read)

    def test_notification_mark_all_read_api(self):
        """Test marking all notifications as read via API."""
        self.client.login(username='testuser', password='testpass123')

        # Create another unread notification
        Notification.objects.create(
            recipient=self.user,
            notification_type='on_deck',
            title='On Deck',
            message='You are next!',
            is_read=False
        )

        response = self.client.post(reverse('notification_mark_all_read_api'))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data['success'])

        # All notifications should now be read
        unread_count = Notification.objects.filter(recipient=self.user, is_read=False).count()
        self.assertEqual(unread_count, 0)


class LegacyViewsTest(TestCase):
    """Test legacy schedule views (for backwards compatibility testing)."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_legacy_schedule_list_requires_login(self):
        """Test that legacy schedule list requires authentication."""
        response = self.client.get(reverse('schedule'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_legacy_schedule_list_accessible(self):
        """Test that legacy schedule list is still accessible."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('schedule'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'legacy_archive/schedule_list.html')

    def test_legacy_create_schedule_get(self):
        """Test GET request to legacy create schedule view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('create_schedule'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'legacy_archive/create_schedule.html')
