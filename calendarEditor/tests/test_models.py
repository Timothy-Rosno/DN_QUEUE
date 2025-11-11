"""
Tests for calendarEditor models.

Coverage:
- Machine: Creation, status management, queue counting, wait time calculations
- QueueEntry: Creation, assignment, status transitions, estimated start time
- QueuePreset: Creation, permissions, display name generation
- Notification: Creation, filtering, read status
- NotificationPreference: Defaults, user preferences
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from calendarEditor.models import (
    Machine, QueueEntry, QueuePreset, Notification, NotificationPreference, ScheduleEntry
)


class MachineModelTest(TestCase):
    """Test Machine model functionality."""

    def setUp(self):
        """Create test machines and users."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.machine1 = Machine.objects.create(
            name='Test Fridge 1',
            min_temp=0.01,
            max_temp=300,
            b_field_x=1.5,
            b_field_y=1.5,
            b_field_z=9.0,
            b_field_direction='parallel_perpendicular',
            dc_lines=12,
            rf_lines=2,
            daughterboard_type='QBoard II',
            optical_capabilities='available',
            cooldown_hours=8,
            current_status='idle',
            is_available=True
        )

    def test_machine_creation(self):
        """Test that machines are created correctly."""
        self.assertEqual(self.machine1.name, 'Test Fridge 1')
        self.assertEqual(self.machine1.min_temp, 0.01)
        self.assertEqual(self.machine1.current_status, 'idle')
        self.assertTrue(self.machine1.is_available)

    def test_machine_string_representation(self):
        """Test machine __str__ method."""
        expected = "Test Fridge 1 (Idle)"
        self.assertEqual(str(self.machine1), expected)

    def test_get_queue_count_empty(self):
        """Test queue count when no entries exist."""
        self.assertEqual(self.machine1.get_queue_count(), 0)

    def test_get_queue_count_with_entries(self):
        """Test queue count with multiple queue entries."""
        QueueEntry.objects.create(
            user=self.user,
            title='Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine1,
            status='queued',
            queue_position=1
        )
        QueueEntry.objects.create(
            user=self.user,
            title='Job 2',
            required_min_temp=0.1,
            estimated_duration_hours=3.0,
            assigned_machine=self.machine1,
            status='queued',
            queue_position=2
        )
        # Create a completed entry (shouldn't be counted)
        QueueEntry.objects.create(
            user=self.user,
            title='Job 3',
            required_min_temp=0.1,
            estimated_duration_hours=1.0,
            assigned_machine=self.machine1,
            status='completed',
            queue_position=None
        )

        self.assertEqual(self.machine1.get_queue_count(), 2)

    def test_get_estimated_wait_time_idle_no_queue(self):
        """Test wait time calculation for idle machine with no queue."""
        wait_time = self.machine1.get_estimated_wait_time()
        self.assertEqual(wait_time, timedelta(0))

    def test_get_estimated_wait_time_with_queue(self):
        """Test wait time calculation with queued jobs."""
        # Create 2 queued jobs (2h + 8h cooldown, 3h + 8h cooldown)
        QueueEntry.objects.create(
            user=self.user,
            title='Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine1,
            status='queued',
            queue_position=1
        )
        QueueEntry.objects.create(
            user=self.user,
            title='Job 2',
            required_min_temp=0.1,
            estimated_duration_hours=3.0,
            assigned_machine=self.machine1,
            status='queued',
            queue_position=2
        )

        # Expected: 2h + 8h + 3h + 8h = 21 hours
        wait_time = self.machine1.get_estimated_wait_time()
        expected_wait = timedelta(hours=21)
        self.assertEqual(wait_time, expected_wait)

    def test_get_estimated_wait_time_running_job(self):
        """Test wait time calculation with running job."""
        # Set machine to have an estimated available time in the future
        future_time = timezone.now() + timedelta(hours=5)
        self.machine1.estimated_available_time = future_time
        self.machine1.current_status = 'running'
        self.machine1.save()

        # Add one queued job
        QueueEntry.objects.create(
            user=self.user,
            title='Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine1,
            status='queued',
            queue_position=1
        )

        # Expected: 5h (current job) + 2h + 8h (queued job + cooldown) = 15h
        wait_time = self.machine1.get_estimated_wait_time()
        expected_wait = timedelta(hours=15)
        # Allow small delta for time calculations
        self.assertAlmostEqual(
            wait_time.total_seconds(),
            expected_wait.total_seconds(),
            delta=60  # 1 minute tolerance
        )


class QueueEntryModelTest(TestCase):
    """Test QueueEntry model functionality."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            b_field_x=1.5,
            b_field_y=1.5,
            b_field_z=9.0,
            cooldown_hours=8,
            current_status='idle',
            is_available=True
        )

    def test_queue_entry_creation(self):
        """Test basic queue entry creation."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Test Experiment',
            description='Testing low temperature behavior',
            required_min_temp=0.1,
            required_max_temp=10.0,
            required_b_field_x=0.5,
            required_dc_lines=6,
            estimated_duration_hours=4.0,
            assigned_machine=self.machine,
            queue_position=1
        )

        self.assertEqual(entry.title, 'Test Experiment')
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.status, 'queued')
        self.assertEqual(entry.assigned_machine, self.machine)

    def test_queue_entry_string_representation(self):
        """Test queue entry __str__ method."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Test Experiment',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine
        )

        expected = "Test Experiment - testuser [Test Fridge] (Queued)"
        self.assertEqual(str(entry), expected)

    def test_queue_entry_without_machine(self):
        """Test queue entry creation without assigned machine."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Unassigned Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0
        )

        self.assertIsNone(entry.assigned_machine)
        expected = "Unassigned Job - testuser [Unassigned] (Queued)"
        self.assertEqual(str(entry), expected)

    def test_calculate_estimated_start_time_no_machine(self):
        """Test estimated start time when no machine is assigned."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Test',
            required_min_temp=0.1,
            estimated_duration_hours=2.0
        )

        self.assertIsNone(entry.calculate_estimated_start_time())

    def test_calculate_estimated_start_time_running_job(self):
        """Test estimated start time for currently running job."""
        start_time = timezone.now()
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Test',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='running',
            started_at=start_time
        )

        self.assertEqual(entry.calculate_estimated_start_time(), start_time)

    def test_calculate_estimated_start_time_first_in_queue(self):
        """Test estimated start time for first position in queue."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Test',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=1
        )

        # Should start approximately now (machine is idle)
        estimated = entry.calculate_estimated_start_time()
        now = timezone.now()
        # Allow 1 minute tolerance
        self.assertLessEqual(abs((estimated - now).total_seconds()), 60)

    def test_calculate_estimated_start_time_with_queue(self):
        """Test estimated start time with jobs ahead in queue."""
        # Create first job
        QueueEntry.objects.create(
            user=self.user,
            title='Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=1
        )

        # Create second job (the one we're testing)
        entry2 = QueueEntry.objects.create(
            user=self.user,
            title='Job 2',
            required_min_temp=0.1,
            estimated_duration_hours=3.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=2
        )

        # Expected: now + 2h (job1) + 8h (cooldown) = 10 hours from now
        estimated = entry2.calculate_estimated_start_time()
        now = timezone.now()
        expected_delay = timedelta(hours=10)

        actual_delay = estimated - now
        # Allow small tolerance
        self.assertAlmostEqual(
            actual_delay.total_seconds(),
            expected_delay.total_seconds(),
            delta=60  # 1 minute tolerance
        )

    def test_rush_job_fields(self):
        """Test rush job related fields."""
        rush_time = timezone.now()
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Urgent Experiment',
            required_min_temp=0.1,
            estimated_duration_hours=1.0,
            assigned_machine=self.machine,
            is_rush_job=True,
            rush_job_submitted_at=rush_time
        )

        self.assertTrue(entry.is_rush_job)
        self.assertEqual(entry.rush_job_submitted_at, rush_time)


class QueuePresetModelTest(TestCase):
    """Test QueuePreset model functionality."""

    def setUp(self):
        """Create test users."""
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')
        self.admin = User.objects.create_user(username='admin', password='testpass123', is_staff=True)

    def test_preset_creation(self):
        """Test basic preset creation."""
        preset = QueuePreset.objects.create(
            name='Low Temp Test',
            creator=self.user1,
            required_min_temp=0.05,
            required_b_field_x=0.5,
            required_dc_lines=6,
            estimated_duration_hours=3.0
        )

        self.assertEqual(preset.name, 'Low Temp Test')
        self.assertEqual(preset.creator, self.user1)
        self.assertFalse(preset.is_public)

    def test_preset_display_name_generation(self):
        """Test automatic display name generation on save."""
        preset = QueuePreset.objects.create(
            name='Test Preset',
            creator=self.user1,
            required_min_temp=0.1
        )

        # Display name should be auto-generated
        self.assertIn('Test Preset', preset.display_name)
        self.assertIn('user1', preset.display_name)
        self.assertIn('Auth.', preset.display_name)
        self.assertIn('Ed.', preset.display_name)

    def test_preset_display_name_after_edit(self):
        """Test display name updates when edited by different user."""
        preset = QueuePreset.objects.create(
            name='Test Preset',
            creator=self.user1,
            required_min_temp=0.1
        )

        # Edit by user2
        preset.last_edited_by = self.user2
        preset.save()

        # Should now show user2 as editor
        self.assertIn('Ed. user2', preset.display_name)
        self.assertIn('Auth. user1', preset.display_name)

    def test_can_edit_as_creator(self):
        """Test that creators can always edit their presets."""
        preset = QueuePreset.objects.create(
            name='Test Preset',
            creator=self.user1,
            required_min_temp=0.1,
            is_public=False
        )

        self.assertTrue(preset.can_edit(self.user1))

    def test_can_edit_as_non_creator_private(self):
        """Test that non-creators cannot edit private presets."""
        preset = QueuePreset.objects.create(
            name='Test Preset',
            creator=self.user1,
            required_min_temp=0.1,
            is_public=False
        )

        self.assertFalse(preset.can_edit(self.user2))

    def test_can_edit_as_admin_public(self):
        """Test that admins can edit public presets."""
        preset = QueuePreset.objects.create(
            name='Test Preset',
            creator=self.user1,
            required_min_temp=0.1,
            is_public=True
        )

        self.assertTrue(preset.can_edit(self.admin))

    def test_can_edit_as_admin_private(self):
        """Test that admins cannot edit private presets they don't own."""
        preset = QueuePreset.objects.create(
            name='Test Preset',
            creator=self.user1,
            required_min_temp=0.1,
            is_public=False
        )

        self.assertFalse(preset.can_edit(self.admin))


class NotificationModelTest(TestCase):
    """Test Notification model functionality."""

    def setUp(self):
        """Create test users and related objects."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.admin = User.objects.create_user(username='admin', password='testpass123', is_staff=True)

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

        self.queue_entry = QueueEntry.objects.create(
            user=self.user,
            title='Test Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine
        )

    def test_notification_creation(self):
        """Test basic notification creation."""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='Job Started',
            message='Your experiment has started running.',
            related_queue_entry=self.queue_entry,
            related_machine=self.machine
        )

        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.notification_type, 'job_started')
        self.assertFalse(notification.is_read)

    def test_notification_string_representation(self):
        """Test notification __str__ method."""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='Job Started',
            message='Test message'
        )

        expected = "testuser - Job Started"
        self.assertEqual(str(notification), expected)

    def test_notification_ordering(self):
        """Test that notifications are ordered by creation time (newest first)."""
        notif1 = Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='First',
            message='First notification'
        )

        notif2 = Notification.objects.create(
            recipient=self.user,
            notification_type='job_completed',
            title='Second',
            message='Second notification'
        )

        notifications = Notification.objects.all()
        self.assertEqual(notifications[0], notif2)  # Newest first
        self.assertEqual(notifications[1], notif1)

    def test_notification_filtering_by_recipient(self):
        """Test filtering notifications by recipient."""
        user2 = User.objects.create_user(username='user2', password='testpass123')

        Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='User 1 Notification',
            message='For user 1'
        )

        Notification.objects.create(
            recipient=user2,
            notification_type='job_started',
            title='User 2 Notification',
            message='For user 2'
        )

        user1_notifications = Notification.objects.filter(recipient=self.user)
        self.assertEqual(user1_notifications.count(), 1)
        self.assertEqual(user1_notifications[0].title, 'User 1 Notification')

    def test_notification_read_status(self):
        """Test notification read status toggling."""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='job_started',
            title='Test',
            message='Test message'
        )

        self.assertFalse(notification.is_read)

        notification.is_read = True
        notification.save()

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)


class NotificationPreferenceModelTest(TestCase):
    """Test NotificationPreference model functionality."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_notification_preference_get_or_create(self):
        """Test get_or_create_for_user class method."""
        prefs = NotificationPreference.get_or_create_for_user(self.user)

        self.assertEqual(prefs.user, self.user)
        # Check defaults
        self.assertTrue(prefs.notify_public_preset_created)
        self.assertTrue(prefs.notify_on_deck)
        self.assertTrue(prefs.email_notifications)
        self.assertTrue(prefs.in_app_notifications)

    def test_notification_preference_defaults(self):
        """Test that default preferences are set correctly."""
        prefs = NotificationPreference.objects.create(user=self.user)

        # Preset notifications (default True)
        self.assertTrue(prefs.notify_public_preset_created)
        self.assertTrue(prefs.notify_public_preset_edited)
        self.assertTrue(prefs.notify_public_preset_deleted)

        # Queue notifications (default True)
        self.assertTrue(prefs.notify_queue_position_change)
        self.assertTrue(prefs.notify_on_deck)
        self.assertTrue(prefs.notify_job_started)
        self.assertTrue(prefs.notify_job_completed)

        # Machine queue notifications (default False)
        self.assertFalse(prefs.notify_machine_queue_changes)

    def test_notification_preference_update(self):
        """Test updating notification preferences."""
        prefs = NotificationPreference.get_or_create_for_user(self.user)

        # Disable some notifications
        prefs.notify_public_preset_created = False
        prefs.notify_on_deck = False
        prefs.email_notifications = False
        prefs.save()

        prefs.refresh_from_db()
        self.assertFalse(prefs.notify_public_preset_created)
        self.assertFalse(prefs.notify_on_deck)
        self.assertFalse(prefs.email_notifications)
        # Others should remain True
        self.assertTrue(prefs.notify_job_started)


class ScheduleEntryModelTest(TestCase):
    """Test legacy ScheduleEntry model (for migration compatibility)."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_schedule_entry_creation(self):
        """Test legacy schedule entry creation."""
        start = timezone.now() + timedelta(hours=2)
        end = start + timedelta(hours=4)

        entry = ScheduleEntry.objects.create(
            user=self.user,
            title='Test Event',
            description='Testing legacy model',
            start_datetime=start,
            end_datetime=end,
            location='Lab 123',
            attendees=2
        )

        self.assertEqual(entry.title, 'Test Event')
        self.assertEqual(entry.status, 'pending')
        self.assertEqual(entry.attendees, 2)

    def test_schedule_entry_is_upcoming(self):
        """Test is_upcoming method."""
        # Future event
        future_start = timezone.now() + timedelta(hours=2)
        future_entry = ScheduleEntry.objects.create(
            user=self.user,
            title='Future Event',
            start_datetime=future_start,
            end_datetime=future_start + timedelta(hours=1)
        )

        # Past event
        past_start = timezone.now() - timedelta(hours=2)
        past_entry = ScheduleEntry.objects.create(
            user=self.user,
            title='Past Event',
            start_datetime=past_start,
            end_datetime=past_start + timedelta(hours=1)
        )

        self.assertTrue(future_entry.is_upcoming())
        self.assertFalse(past_entry.is_upcoming())
