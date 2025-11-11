"""
Tests for the machine matching algorithm.

Coverage:
- find_best_machine: Temperature, B-field, connections, daughterboard, optical matching
- assign_to_queue: Automatic machine assignment and queue positioning
- get_matching_machines: Compatible machine listing
- reorder_queue: Queue reordering after entry removal
- move_queue_entry_up/down: Queue position swapping
- set_queue_position: Direct queue position setting
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from calendarEditor.models import Machine, QueueEntry
from calendarEditor.matching_algorithm import (
    find_best_machine,
    assign_to_queue,
    get_matching_machines,
    reorder_queue,
    move_queue_entry_up,
    move_queue_entry_down,
    set_queue_position
)


class FindBestMachineTest(TestCase):
    """Test the find_best_machine algorithm."""

    def setUp(self):
        """Create test machines and user."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Create machines with different capabilities
        self.low_temp_machine = Machine.objects.create(
            name='Low Temp Fridge',
            min_temp=0.01,
            max_temp=300,
            b_field_x=1.0,
            b_field_y=1.0,
            b_field_z=9.0,
            b_field_direction='parallel_perpendicular',
            dc_lines=12,
            rf_lines=2,
            daughterboard_type='QBoard II',
            optical_capabilities='available',
            cooldown_hours=8
        )

        self.high_temp_machine = Machine.objects.create(
            name='High Temp Fridge',
            min_temp=0.05,  # Can't go as low
            max_temp=300,
            b_field_x=2.0,
            b_field_y=2.0,
            b_field_z=12.0,
            b_field_direction='perpendicular',
            dc_lines=16,
            rf_lines=4,
            daughterboard_type='QBoard I',
            optical_capabilities='none',
            cooldown_hours=6
        )

        self.basic_machine = Machine.objects.create(
            name='Basic Fridge',
            min_temp=0.1,
            max_temp=300,
            b_field_x=0.5,
            b_field_y=0.5,
            b_field_z=3.0,
            b_field_direction='parallel',
            dc_lines=8,
            rf_lines=1,
            daughterboard_type='Montana Puck',
            optical_capabilities='under_construction',
            cooldown_hours=4
        )

    def test_find_best_machine_temperature_requirement(self):
        """Test that machines are filtered by temperature capability."""
        # Request very low temperature - only low_temp_machine qualifies
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Low Temp Experiment',
            required_min_temp=0.02,  # Needs to go to 0.02K
            estimated_duration_hours=2.0
        )

        best_machine = find_best_machine(entry)
        self.assertEqual(best_machine, self.low_temp_machine)

    def test_find_best_machine_max_temperature_requirement(self):
        """Test filtering by maximum temperature requirement."""
        # Most machines can handle low min temp, but let's test max temp filtering
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Test',
            required_min_temp=0.1,
            required_max_temp=250,  # All machines should handle this
            estimated_duration_hours=2.0
        )

        best_machine = find_best_machine(entry)
        self.assertIsNotNone(best_machine)

    def test_find_best_machine_b_field_requirement(self):
        """Test that machines are filtered by B-field capability."""
        # Request high B-field - only high_temp_machine has strong enough field
        entry = QueueEntry.objects.create(
            user=self.user,
            title='High Field Experiment',
            required_min_temp=0.1,
            required_b_field_x=1.5,
            required_b_field_y=1.5,
            required_b_field_z=10.0,
            estimated_duration_hours=2.0
        )

        best_machine = find_best_machine(entry)
        self.assertEqual(best_machine, self.high_temp_machine)

    def test_find_best_machine_b_field_direction_requirement(self):
        """Test filtering by B-field direction."""
        # Request parallel_perpendicular - only low_temp_machine has both
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Directional Field Test',
            required_min_temp=0.1,
            required_b_field_x=0.5,
            required_b_field_direction='parallel_perpendicular',
            estimated_duration_hours=2.0
        )

        best_machine = find_best_machine(entry)
        self.assertEqual(best_machine, self.low_temp_machine)

    def test_find_best_machine_perpendicular_only(self):
        """Test that parallel_perpendicular machine can fulfill perpendicular-only request."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Perpendicular Test',
            required_min_temp=0.1,
            required_b_field_direction='perpendicular',
            estimated_duration_hours=2.0
        )

        # Both low_temp_machine (parallel_perpendicular) and high_temp_machine (perpendicular) qualify
        best_machine = find_best_machine(entry)
        self.assertIn(best_machine, [self.low_temp_machine, self.high_temp_machine])

    def test_find_best_machine_dc_rf_lines_requirement(self):
        """Test filtering by DC/RF line requirements."""
        # Request many DC/RF lines - only high_temp_machine has enough
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Many Connections',
            required_min_temp=0.1,
            required_dc_lines=14,
            required_rf_lines=3,
            estimated_duration_hours=2.0
        )

        best_machine = find_best_machine(entry)
        self.assertEqual(best_machine, self.high_temp_machine)

    def test_find_best_machine_daughterboard_requirement(self):
        """Test filtering by daughterboard requirement."""
        # Request Montana Puck - only basic_machine has it
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Montana Puck Experiment',
            required_min_temp=0.1,
            required_daughterboard='Montana Puck',
            estimated_duration_hours=2.0
        )

        best_machine = find_best_machine(entry)
        self.assertEqual(best_machine, self.basic_machine)

    def test_find_best_machine_no_match(self):
        """Test that None is returned when no machine matches."""
        # Request impossible requirements
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Impossible Request',
            required_min_temp=0.001,  # Colder than any machine can go
            required_b_field_z=20.0,  # Higher than any machine's field
            estimated_duration_hours=2.0
        )

        best_machine = find_best_machine(entry)
        self.assertIsNone(best_machine)

    def test_find_best_machine_selects_earliest_available(self):
        """Test that algorithm selects machine with shortest wait time."""
        # Create queue entries for low_temp_machine (8h cooldown)
        QueueEntry.objects.create(
            user=self.user,
            title='Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=10.0,  # 10h + 8h cooldown = 18h wait
            assigned_machine=self.low_temp_machine,
            status='queued',
            queue_position=1
        )

        # Create smaller queue entry for basic_machine (4h cooldown)
        QueueEntry.objects.create(
            user=self.user,
            title='Job 2',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,  # 2h + 4h cooldown = 6h wait
            assigned_machine=self.basic_machine,
            status='queued',
            queue_position=1
        )

        # New request that both machines can handle
        entry = QueueEntry.objects.create(
            user=self.user,
            title='New Request',
            required_min_temp=0.1,
            required_b_field_x=0.3,
            estimated_duration_hours=1.0
        )

        # Should select basic_machine because it will be available sooner
        best_machine = find_best_machine(entry)
        self.assertEqual(best_machine, self.basic_machine)

    def test_find_best_machine_with_details(self):
        """Test that return_details parameter provides matching information."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Test',
            required_min_temp=0.1,
            required_b_field_x=0.5,
            estimated_duration_hours=2.0
        )

        machine, details = find_best_machine(entry, return_details=True)

        self.assertIsNotNone(machine)
        self.assertIn('total_machines', details)
        self.assertIn('temp_compatible', details)
        self.assertIn('field_compatible', details)
        self.assertIn('availability_times', details)
        self.assertIn('selected_machine', details)


class AssignToQueueTest(TestCase):
    """Test the assign_to_queue function."""

    def setUp(self):
        """Create test data."""
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
            cooldown_hours=8
        )

    def test_assign_to_queue_first_entry(self):
        """Test assigning first entry to empty queue."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='First Job',
            required_min_temp=0.1,
            estimated_duration_hours=2.0
        )

        success = assign_to_queue(entry)

        self.assertTrue(success)
        entry.refresh_from_db()
        self.assertEqual(entry.assigned_machine, self.machine)
        self.assertEqual(entry.queue_position, 1)
        self.assertIsNotNone(entry.estimated_start_time)

    def test_assign_to_queue_multiple_entries(self):
        """Test assigning multiple entries maintains correct queue positions."""
        # Create first entry
        entry1 = QueueEntry.objects.create(
            user=self.user,
            title='Job 1',
            required_min_temp=0.1,
            estimated_duration_hours=2.0
        )
        assign_to_queue(entry1)

        # Create second entry
        entry2 = QueueEntry.objects.create(
            user=self.user,
            title='Job 2',
            required_min_temp=0.1,
            estimated_duration_hours=3.0
        )
        assign_to_queue(entry2)

        entry1.refresh_from_db()
        entry2.refresh_from_db()

        self.assertEqual(entry1.queue_position, 1)
        self.assertEqual(entry2.queue_position, 2)
        self.assertEqual(entry1.assigned_machine, entry2.assigned_machine)

    def test_assign_to_queue_no_matching_machine(self):
        """Test assignment fails when no machine matches requirements."""
        entry = QueueEntry.objects.create(
            user=self.user,
            title='Impossible Job',
            required_min_temp=0.001,  # Too cold
            estimated_duration_hours=2.0
        )

        success = assign_to_queue(entry)

        self.assertFalse(success)
        entry.refresh_from_db()
        self.assertIsNone(entry.assigned_machine)
        self.assertIsNone(entry.queue_position)


class GetMatchingMachinesTest(TestCase):
    """Test the get_matching_machines function."""

    def setUp(self):
        """Create test machines."""
        self.machine1 = Machine.objects.create(
            name='Low Temp',
            min_temp=0.01,
            max_temp=300,
            b_field_x=1.0,
            b_field_y=1.0,
            b_field_z=9.0,
            cooldown_hours=8
        )

        self.machine2 = Machine.objects.create(
            name='High Field',
            min_temp=0.05,
            max_temp=300,
            b_field_x=3.0,
            b_field_y=3.0,
            b_field_z=15.0,
            cooldown_hours=6
        )

    def test_get_matching_machines_temperature_only(self):
        """Test getting machines by temperature requirement."""
        machines = get_matching_machines(required_min_temp=0.02)

        self.assertEqual(machines.count(), 1)
        self.assertEqual(machines.first(), self.machine1)

    def test_get_matching_machines_with_b_field(self):
        """Test getting machines by temperature and B-field requirements."""
        machines = get_matching_machines(
            required_min_temp=0.1,
            required_b_field_z=10.0
        )

        self.assertEqual(machines.count(), 1)
        self.assertEqual(machines.first(), self.machine2)

    def test_get_matching_machines_all_match(self):
        """Test getting machines when all match requirements."""
        machines = get_matching_machines(
            required_min_temp=0.1,
            required_b_field_x=0.5
        )

        self.assertEqual(machines.count(), 2)


class ReorderQueueTest(TestCase):
    """Test queue reordering functionality."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

        # Create queue entries with gaps in positions
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
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=5  # Gap in positions
        )

    def test_reorder_queue_fixes_gaps(self):
        """Test that reorder_queue fixes gaps in queue positions."""
        reorder_queue(self.machine)

        self.entry1.refresh_from_db()
        self.entry2.refresh_from_db()

        self.assertEqual(self.entry1.queue_position, 1)
        self.assertEqual(self.entry2.queue_position, 2)  # Gap fixed


class MoveQueueEntryTest(TestCase):
    """Test moving queue entries up and down."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
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
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=2
        )

        self.entry3 = QueueEntry.objects.create(
            user=self.user,
            title='Job 3',
            required_min_temp=0.1,
            estimated_duration_hours=2.0,
            assigned_machine=self.machine,
            status='queued',
            queue_position=3
        )

    def test_move_queue_entry_up(self):
        """Test moving an entry up in the queue."""
        success = move_queue_entry_up(self.entry2.id)

        self.assertTrue(success)
        self.entry1.refresh_from_db()
        self.entry2.refresh_from_db()

        self.assertEqual(self.entry2.queue_position, 1)
        self.assertEqual(self.entry1.queue_position, 2)

    def test_move_queue_entry_up_already_first(self):
        """Test that moving first entry up returns False."""
        success = move_queue_entry_up(self.entry1.id)

        self.assertFalse(success)
        self.entry1.refresh_from_db()
        self.assertEqual(self.entry1.queue_position, 1)

    def test_move_queue_entry_down(self):
        """Test moving an entry down in the queue."""
        success = move_queue_entry_down(self.entry2.id)

        self.assertTrue(success)
        self.entry2.refresh_from_db()
        self.entry3.refresh_from_db()

        self.assertEqual(self.entry2.queue_position, 3)
        self.assertEqual(self.entry3.queue_position, 2)

    def test_move_queue_entry_down_already_last(self):
        """Test that moving last entry down returns False."""
        success = move_queue_entry_down(self.entry3.id)

        self.assertFalse(success)
        self.entry3.refresh_from_db()
        self.assertEqual(self.entry3.queue_position, 3)


class SetQueuePositionTest(TestCase):
    """Test setting queue entry to specific position."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.machine = Machine.objects.create(
            name='Test Fridge',
            min_temp=0.01,
            max_temp=300,
            cooldown_hours=8
        )

        self.entries = []
        for i in range(1, 6):
            entry = QueueEntry.objects.create(
                user=self.user,
                title=f'Job {i}',
                required_min_temp=0.1,
                estimated_duration_hours=2.0,
                assigned_machine=self.machine,
                status='queued',
                queue_position=i
            )
            self.entries.append(entry)

    def test_set_queue_position_move_to_front(self):
        """Test moving entry from middle to front of queue."""
        # Move entry at position 3 to position 1
        success = set_queue_position(self.entries[2].id, 1)

        self.assertTrue(success)

        # Refresh all entries
        for entry in self.entries:
            entry.refresh_from_db()

        # Entry 3 should now be at position 1
        self.assertEqual(self.entries[2].queue_position, 1)
        # Previous entries should be shifted down
        self.assertEqual(self.entries[0].queue_position, 2)
        self.assertEqual(self.entries[1].queue_position, 3)

    def test_set_queue_position_move_to_back(self):
        """Test moving entry from front to back of queue."""
        # Move entry at position 1 to position 5
        success = set_queue_position(self.entries[0].id, 5)

        self.assertTrue(success)

        for entry in self.entries:
            entry.refresh_from_db()

        # Entry 1 should now be at position 5
        self.assertEqual(self.entries[0].queue_position, 5)
        # Other entries should be shifted up
        self.assertEqual(self.entries[1].queue_position, 1)

    def test_set_queue_position_invalid_position(self):
        """Test that invalid positions return False."""
        # Try to set position to 0 or negative
        success = set_queue_position(self.entries[0].id, 0)
        self.assertFalse(success)

        success = set_queue_position(self.entries[0].id, -1)
        self.assertFalse(success)

    def test_set_queue_position_beyond_max(self):
        """Test that position beyond max is clamped to max."""
        # Try to set position to 100 (beyond max)
        success = set_queue_position(self.entries[0].id, 100)

        self.assertTrue(success)  # Should succeed but clamp to max
        self.entries[0].refresh_from_db()
        self.assertEqual(self.entries[0].queue_position, 5)  # Max position
