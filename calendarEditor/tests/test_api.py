"""
Tests for API endpoints.

Coverage:
- Preset API: load_preset_ajax, get_editable_presets_ajax, get_viewable_presets_ajax
- Notification API: notification_list_api, notification_mark_read_api, notification_mark_all_read_api
- Error handling and permissions
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json

from calendarEditor.models import QueuePreset, Notification, NotificationPreference


class PresetAPITest(TestCase):
    """Test preset-related API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.other_user = User.objects.create_user(username='otheruser', password='testpass123')

        # Create private preset owned by user
        self.private_preset = QueuePreset.objects.create(
            name='Private Preset',
            creator=self.user,
            is_public=False,
            required_min_temp=0.1,
            required_dc_lines=6
        )

        # Create public preset
        self.public_preset = QueuePreset.objects.create(
            name='Public Preset',
            creator=self.user,
            is_public=True,
            required_min_temp=0.05,
            required_b_field_x=1.5
        )

    def test_load_preset_ajax_own_preset(self):
        """Test loading own preset via AJAX."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('load_preset', args=[self.private_preset.id]))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(data['preset']['name'], 'Private Preset')
        self.assertEqual(float(data['preset']['required_min_temp']), 0.1)

    def test_load_preset_ajax_public_preset(self):
        """Test loading public preset via AJAX."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.get(reverse('load_preset', args=[self.public_preset.id]))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(data['preset']['name'], 'Public Preset')

    def test_load_preset_ajax_unauthorized(self):
        """Test that loading someone else's private preset fails."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.get(reverse('load_preset', args=[self.private_preset.id]))

        # Should return error or 404
        self.assertIn(response.status_code, [403, 404])

    def test_load_preset_ajax_not_logged_in(self):
        """Test that loading preset requires authentication."""
        response = self.client.get(reverse('load_preset', args=[self.private_preset.id]))

        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_get_editable_presets_ajax(self):
        """Test getting list of editable presets."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('get_editable_presets'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        # Should include both private and public presets owned by user
        self.assertEqual(len(data['presets']), 2)

    def test_get_editable_presets_ajax_other_user(self):
        """Test that other users see only their editable presets."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.get(reverse('get_editable_presets'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        # Other user should not see testuser's presets
        self.assertEqual(len(data['presets']), 0)

    def test_get_viewable_presets_ajax(self):
        """Test getting list of viewable presets."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.get(reverse('get_viewable_presets'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        # Should only see public preset
        self.assertEqual(len(data['presets']), 1)
        self.assertEqual(data['presets'][0]['name'], 'Public Preset')


class NotificationAPITest(TestCase):
    """Test notification API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.other_user = User.objects.create_user(username='otheruser', password='testpass123')

        # Create notifications for user
        self.notif1 = Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='Job 1 Started',
            message='Your job has started',
            is_read=False
        )

        self.notif2 = Notification.objects.create(
            recipient=self.user,
            notification_type='job_completed',
            title='Job 2 Completed',
            message='Your job has completed',
            is_read=False
        )

        self.notif3 = Notification.objects.create(
            recipient=self.user,
            notification_type='on_deck',
            title='On Deck',
            message='You are next!',
            is_read=True  # Already read
        )

    def test_notification_list_api(self):
        """Test fetching notification list."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('notification_list_api'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(len(data['notifications']), 3)
        self.assertEqual(data['unread_count'], 2)

        # Check notification structure
        first_notif = data['notifications'][0]
        self.assertIn('id', first_notif)
        self.assertIn('title', first_notif)
        self.assertIn('message', first_notif)
        self.assertIn('notification_type', first_notif)
        self.assertIn('is_read', first_notif)
        self.assertIn('created_at', first_notif)

    def test_notification_list_api_not_logged_in(self):
        """Test that notification list requires authentication."""
        response = self.client.get(reverse('notification_list_api'))

        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_notification_mark_read_api(self):
        """Test marking notification as read."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('notification_mark_read_api'),
            data=json.dumps({'notification_id': self.notif1.id}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])

        # Verify notification is now read
        self.notif1.refresh_from_db()
        self.assertTrue(self.notif1.is_read)

    def test_notification_mark_read_api_invalid_id(self):
        """Test marking non-existent notification as read."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('notification_mark_read_api'),
            data=json.dumps({'notification_id': 99999}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_notification_mark_read_api_other_user(self):
        """Test that user cannot mark another user's notification as read."""
        self.client.login(username='otheruser', password='testpass123')

        response = self.client.post(
            reverse('notification_mark_read_api'),
            data=json.dumps({'notification_id': self.notif1.id}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertFalse(data['success'])

        # Verify notification is still unread
        self.notif1.refresh_from_db()
        self.assertFalse(self.notif1.is_read)

    def test_notification_mark_all_read_api(self):
        """Test marking all notifications as read."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('notification_mark_all_read_api'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])

        # Verify all notifications are now read
        unread_count = Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).count()
        self.assertEqual(unread_count, 0)

    def test_notification_mark_all_read_api_not_logged_in(self):
        """Test that mark all read requires authentication."""
        response = self.client.post(reverse('notification_mark_all_read_api'))

        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_notification_mark_read_api_missing_id(self):
        """Test marking notification without providing ID."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('notification_mark_read_api'),
            data=json.dumps({}),  # No notification_id
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_notification_api_get_method_not_allowed(self):
        """Test that mark read API only accepts POST."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('notification_mark_read_api'))

        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)


class APIErrorHandlingTest(TestCase):
    """Test API error handling and edge cases."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_api_handles_malformed_json(self):
        """Test that API handles malformed JSON gracefully."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('notification_mark_read_api'),
            data='{"invalid json}',
            content_type='application/json'
        )

        # Should return error response, not crash
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_api_requires_json_content_type(self):
        """Test that API expects application/json content type."""
        self.client.login(username='testuser', password='testpass123')

        # Send JSON data without proper content type
        response = self.client.post(
            reverse('notification_mark_read_api'),
            data='{"notification_id": 1}'
        )

        # Should handle gracefully
        self.assertIn(response.status_code, [200, 400])


class APIPerformanceTest(TestCase):
    """Test API performance with larger datasets."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_notification_list_with_many_notifications(self):
        """Test notification list API with many notifications."""
        # Create 100 notifications
        for i in range(100):
            Notification.objects.create(
                recipient=self.user,
                notification_type='job_started',
                title=f'Notification {i}',
                message=f'Message {i}',
                is_read=(i % 2 == 0)  # Half read, half unread
            )

        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('notification_list_api'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(len(data['notifications']), 100)
        self.assertEqual(data['unread_count'], 50)

    def test_preset_list_with_many_presets(self):
        """Test preset list API with many presets."""
        # Create 50 presets
        for i in range(50):
            QueuePreset.objects.create(
                name=f'Preset {i}',
                creator=self.user,
                is_public=(i % 3 == 0),  # Some public, some private
                required_min_temp=0.1
            )

        self.client.login(username='testuser', password='testpass123')

        response = self.client.get(reverse('get_editable_presets'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(len(data['presets']), 50)
