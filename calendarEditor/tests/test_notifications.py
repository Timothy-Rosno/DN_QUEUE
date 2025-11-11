"""
Tests for the notification system.

Coverage:
- create_notification: Basic notification creation and WebSocket sending
- notify_preset_created: Public preset creation notifications
- notify_preset_edited: Preset edit notifications (public and private)
- notify_preset_deleted: Preset deletion notifications
- notify_on_deck: ON DECK notifications for queue position #1
- notify_queue_position_change: Queue position change notifications
- notify_machine_queue_addition: New entry to machine queue notifications
- notify_job_started: Job start notifications
- notify_job_completed: Job completion notifications
- check_and_notify_on_deck_status: Automatic ON DECK checking
- get_unread_count: Unread notification counting
- mark_notification_read: Marking notifications as read
- mark_all_read: Bulk marking as read
"""
from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock

from calendarEditor.models import (
    Machine, QueueEntry, QueuePreset, Notification, NotificationPreference
)
from calendarEditor import notifications


class CreateNotificationTest(TestCase):
    """Test basic notification creation."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_create_notification(self, mock_channel_layer):
        """Test creating a basic notification."""
        # Mock the channel layer
        mock_channel_layer.return_value = MagicMock()

        notification = notifications.create_notification(
            recipient=self.user,
            notification_type='job_started',
            title='Test Notification',
            message='This is a test message'
        )

        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.notification_type, 'job_started')
        self.assertEqual(notification.title, 'Test Notification')
        self.assertFalse(notification.is_read)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_create_notification_with_related_objects(self, mock_channel_layer):
        """Test creating notification with related objects."""
        mock_channel_layer.return_value = MagicMock()

        machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

        queue_entry = QueueEntry.objects.create(
            user=self.user,
            title='Test Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=machine
        )

        notification = notifications.create_notification(
            recipient=self.user,
            notification_type='job_started',
            title='Job Started',
            message='Your job has started',
            related_queue_entry=queue_entry,
            related_machine=machine
        )

        self.assertEqual(notification.related_queue_entry, queue_entry)
        self.assertEqual(notification.related_machine, machine)


class PresetNotificationsTest(TestCase):
    """Test preset-related notifications."""

    def setUp(self):
        """Create test users."""
        self.creator = User.objects.create_user(username='creator', password='testpass123')
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')

        # Ensure notification preferences exist with defaults
        NotificationPreference.get_or_create_for_user(self.user1)
        NotificationPreference.get_or_create_for_user(self.user2)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_preset_created_public(self, mock_channel_layer):
        """Test notifications when public preset is created."""
        mock_channel_layer.return_value = MagicMock()

        preset = QueuePreset.objects.create(
            name='Public Preset',
            creator=self.creator,
            is_public=True,
            required_min_temp=0.1
        )

        notifications.notify_preset_created(preset, self.creator)

        # Should create notifications for user1 and user2, but NOT creator
        notif_count = Notification.objects.filter(notification_type='preset_created').count()
        self.assertEqual(notif_count, 2)

        # Verify creator didn't get notification
        creator_notif = Notification.objects.filter(recipient=self.creator).exists()
        self.assertFalse(creator_notif)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_preset_created_private(self, mock_channel_layer):
        """Test that private preset creation doesn't notify anyone."""
        mock_channel_layer.return_value = MagicMock()

        preset = QueuePreset.objects.create(
            name='Private Preset',
            creator=self.creator,
            is_public=False,
            required_min_temp=0.1
        )

        notifications.notify_preset_created(preset, self.creator)

        # Should not create any notifications
        notif_count = Notification.objects.filter(notification_type='preset_created').count()
        self.assertEqual(notif_count, 0)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_preset_edited_public(self, mock_channel_layer):
        """Test notifications when public preset is edited."""
        mock_channel_layer.return_value = MagicMock()

        preset = QueuePreset.objects.create(
            name='Public Preset',
            creator=self.creator,
            is_public=True,
            required_min_temp=0.1
        )

        notifications.notify_preset_edited(preset, self.user1)

        # Should notify creator and user2, but NOT user1 (editor)
        notif_count = Notification.objects.filter(notification_type='preset_edited').count()
        self.assertEqual(notif_count, 2)

        user1_notif = Notification.objects.filter(recipient=self.user1).exists()
        self.assertFalse(user1_notif)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_preset_edited_private_by_other(self, mock_channel_layer):
        """Test notification when someone else edits your private preset."""
        mock_channel_layer.return_value = MagicMock()

        preset = QueuePreset.objects.create(
            name='Private Preset',
            creator=self.creator,
            is_public=False,
            required_min_temp=0.1
        )

        notifications.notify_preset_edited(preset, self.user1)

        # Should only notify the creator
        notif_count = Notification.objects.filter(notification_type='preset_edited').count()
        self.assertEqual(notif_count, 1)

        creator_notif = Notification.objects.filter(recipient=self.creator).first()
        self.assertIsNotNone(creator_notif)
        self.assertIn('private preset', creator_notif.message.lower())

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_preset_deleted(self, mock_channel_layer):
        """Test notifications when preset is deleted."""
        mock_channel_layer.return_value = MagicMock()

        preset_data = {
            'display_name': 'Test Preset',
            'is_public': True,
            'creator_id': self.creator.id
        }

        notifications.notify_preset_deleted(preset_data, self.user1)

        # Should notify all users except user1
        notif_count = Notification.objects.filter(notification_type='preset_deleted').count()
        self.assertEqual(notif_count, 2)


class QueueNotificationsTest(TestCase):
    """Test queue-related notifications."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Ensure notification preferences exist
        NotificationPreference.get_or_create_for_user(self.user)

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
            queue_position=2
        )

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_on_deck(self, mock_channel_layer):
        """Test ON DECK notification."""
        mock_channel_layer.return_value = MagicMock()

        # Move entry to position 1
        self.entry.queue_position = 1
        self.entry.save()

        notifications.notify_on_deck(self.entry)

        # Should create ON DECK notification
        notif = Notification.objects.filter(
            recipient=self.user,
            notification_type='on_deck'
        ).first()

        self.assertIsNotNone(notif)
        self.assertIn('ON DECK', notif.title)
        self.assertIn('#1', notif.message)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_queue_position_change(self, mock_channel_layer):
        """Test queue position change notification."""
        mock_channel_layer.return_value = MagicMock()

        notifications.notify_queue_position_change(self.entry, old_position=5, new_position=2)

        notif = Notification.objects.filter(
            recipient=self.user,
            notification_type='queue_moved'
        ).first()

        self.assertIsNotNone(notif)
        self.assertIn('Position Changed', notif.title)
        self.assertIn('#5', notif.message)
        self.assertIn('#2', notif.message)
        self.assertIn('up', notif.message.lower())

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_machine_queue_addition(self, mock_channel_layer):
        """Test notification when new entry is added to machine queue."""
        mock_channel_layer.return_value = MagicMock()

        # Create another user with entry in same machine queue
        other_user = User.objects.create_user(username='otheruser', password='testpass123')
        NotificationPreference.objects.create(
            user=other_user,
            notify_machine_queue_changes=True  # Enable this notification
        )

        QueueEntry.objects.create(
            user=other_user,
            title='Other Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=1
        )

        # Add new entry to queue
        new_entry = QueueEntry.objects.create(
            user=self.user,
            title='New Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=3
        )

        notifications.notify_machine_queue_addition(new_entry, self.user)

        # Should notify other_user
        notif = Notification.objects.filter(
            recipient=other_user,
            notification_type='queue_added'
        ).first()

        self.assertIsNotNone(notif)
        self.assertIn('New Entry Added', notif.title)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_job_started(self, mock_channel_layer):
        """Test job started notification."""
        mock_channel_layer.return_value = MagicMock()

        notifications.notify_job_started(self.entry)

        notif = Notification.objects.filter(
            recipient=self.user,
            notification_type='job_started'
        ).first()

        self.assertIsNotNone(notif)
        self.assertIn('Started', notif.title)
        self.assertIn('running', notif.message.lower())

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notify_job_completed(self, mock_channel_layer):
        """Test job completed notification."""
        mock_channel_layer.return_value = MagicMock()

        notifications.notify_job_completed(self.entry)

        notif = Notification.objects.filter(
            recipient=self.user,
            notification_type='job_completed'
        ).first()

        self.assertIsNotNone(notif)
        self.assertIn('Completed', notif.title)
        self.assertIn('completed', notif.message.lower())

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_check_and_notify_on_deck_status(self, mock_channel_layer):
        """Test automatic ON DECK checking after queue reorder."""
        mock_channel_layer.return_value = MagicMock()

        # Set entry to position 1
        self.entry.queue_position = 1
        self.entry.save()

        notifications.check_and_notify_on_deck_status(self.machine)

        # Should create ON DECK notification
        notif = Notification.objects.filter(
            recipient=self.user,
            notification_type='on_deck'
        ).first()

        self.assertIsNotNone(notif)


class NotificationPreferenceTest(TestCase):
    """Test that notification preferences are respected."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

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

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_notification_disabled_by_preference(self, mock_channel_layer):
        """Test that notifications are not sent when user disables them."""
        mock_channel_layer.return_value = MagicMock()

        # Disable ON DECK notifications
        prefs = NotificationPreference.get_or_create_for_user(self.user)
        prefs.notify_on_deck = False
        prefs.save()

        notifications.notify_on_deck(self.entry)

        # Should NOT create notification
        notif_count = Notification.objects.filter(
            recipient=self.user,
            notification_type='on_deck'
        ).count()

        self.assertEqual(notif_count, 0)

    @patch('calendarEditor.notifications.get_channel_layer')
    def test_in_app_notifications_disabled(self, mock_channel_layer):
        """Test that in-app notifications can be disabled."""
        mock_channel_layer.return_value = MagicMock()

        # Disable in-app notifications entirely
        prefs = NotificationPreference.get_or_create_for_user(self.user)
        prefs.in_app_notifications = False
        prefs.save()

        notifications.notify_job_started(self.entry)

        # Should NOT create notification
        notif_count = Notification.objects.filter(recipient=self.user).count()
        self.assertEqual(notif_count, 0)


class NotificationUtilityFunctionsTest(TestCase):
    """Test notification utility functions."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Create some notifications
        Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='Job 1 Started',
            message='Message 1',
            is_read=False
        )

        Notification.objects.create(
            recipient=self.user,
            notification_type='job_completed',
            title='Job 2 Completed',
            message='Message 2',
            is_read=False
        )

        Notification.objects.create(
            recipient=self.user,
            notification_type='on_deck',
            title='On Deck',
            message='Message 3',
            is_read=True  # Already read
        )

    def test_get_unread_count(self):
        """Test getting unread notification count."""
        count = notifications.get_unread_count(self.user)
        self.assertEqual(count, 2)

    def test_mark_notification_read(self):
        """Test marking a single notification as read."""
        notif = Notification.objects.filter(recipient=self.user, is_read=False).first()

        success = notifications.mark_notification_read(notif.id, self.user)

        self.assertTrue(success)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_notification_read_wrong_user(self):
        """Test that user can't mark another user's notification as read."""
        other_user = User.objects.create_user(username='otheruser', password='testpass123')
        notif = Notification.objects.filter(recipient=self.user).first()

        success = notifications.mark_notification_read(notif.id, other_user)

        self.assertFalse(success)
        notif.refresh_from_db()
        self.assertFalse(notif.is_read)

    def test_mark_all_read(self):
        """Test marking all notifications as read."""
        notifications.mark_all_read(self.user)

        unread_count = Notification.objects.filter(recipient=self.user, is_read=False).count()
        self.assertEqual(unread_count, 0)

        total_count = Notification.objects.filter(recipient=self.user).count()
        self.assertEqual(total_count, 3)  # All notifications still exist
