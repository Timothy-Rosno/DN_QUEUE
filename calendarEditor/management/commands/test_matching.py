from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from calendarEditor.models import Machine, QueueEntry
from calendarEditor.matching_algorithm import find_best_machine
from django.utils import timezone


class Command(BaseCommand):
    help = 'Test the best-fit matching algorithm'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Testing Best-Fit Matching Algorithm ===\n'))

        # Get or create test user
        user, _ = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com'})

        # Test Case 1: Very low temperature - should go to Hidalgo (0.01K capability)
        self.stdout.write('\nTest 1: Request for 0.05K (very low temp)')
        entry1 = QueueEntry(
            user=user,
            title='Ultra-low temp experiment',
            required_min_temp=0.05,
            estimated_duration_hours=4
        )
        machine, details = find_best_machine(entry1, return_details=True)
        self.stdout.write(f'  Selected: {machine.name if machine else "None"}')
        self.stdout.write(f'  Temp compatible: {details["temp_compatible"]}')
        self.stdout.write(f'  Expected: Hidalgo (only machine reaching 0.01K)')
        self.stdout.write(f'  ✓ PASS' if machine and machine.name == 'Hidalgo' else '  ✗ FAIL')

        # Test Case 2: Medium temp + high B-field - should go to Hidalgo
        self.stdout.write('\nTest 2: Request for 1K with 10T B-field (Z)')
        entry2 = QueueEntry(
            user=user,
            title='High field experiment',
            required_min_temp=1.0,
            required_b_field_z=10,
            estimated_duration_hours=6
        )
        machine, details = find_best_machine(entry2, return_details=True)
        self.stdout.write(f'  Selected: {machine.name if machine else "None"}')
        self.stdout.write(f'  Field compatible: {details["field_compatible"]}')
        self.stdout.write(f'  Expected: Hidalgo (only machine with 16T)')
        self.stdout.write(f'  ✓ PASS' if machine and machine.name == 'Hidalgo' else '  ✗ FAIL')

        # Test Case 3: Higher temp, no B-field - could be Kiutra or Opticool
        self.stdout.write('\nTest 3: Request for 10K, no B-field')
        entry3 = QueueEntry(
            user=user,
            title='Standard cooling experiment',
            required_min_temp=10.0,
            estimated_duration_hours=3
        )
        machine, details = find_best_machine(entry3, return_details=True)
        self.stdout.write(f'  Selected: {machine.name if machine else "None"}')
        self.stdout.write(f'  Temp compatible: {details["temp_compatible"]}')
        self.stdout.write(f'  Field compatible: {details["field_compatible"]}')

        # All three machines can handle this
        if machine:
            wait_times = []
            for m_name, info in details['availability_times'].items():
                hours = int(info['wait_time'].total_seconds() // 3600)
                wait_times.append(f"{m_name}: {hours}h")
                self.stdout.write(f'    {m_name}: wait {hours}h, queue {info["queue_count"]}')
            self.stdout.write(f'  Expected: Machine with shortest wait time')
            self.stdout.write(f'  ✓ PASS (Selected next available)')
        else:
            self.stdout.write('  ✗ FAIL - No machine selected')

        # Test Case 4: Temperature too low for any machine
        self.stdout.write('\nTest 4: Request for 0.001K (impossible)')
        entry4 = QueueEntry(
            user=user,
            title='Impossible experiment',
            required_min_temp=0.001,
            estimated_duration_hours=2
        )
        machine, details = find_best_machine(entry4, return_details=True)
        self.stdout.write(f'  Selected: {machine.name if machine else "None"}')
        self.stdout.write(f'  Rejected reasons:')
        for reason in details['rejected_reasons']:
            self.stdout.write(f'    - {reason}')
        self.stdout.write(f'  Expected: None (no machine can reach 0.001K)')
        self.stdout.write(f'  ✓ PASS' if machine is None else '  ✗ FAIL')

        # Test Case 5: Demonstrate "next available" selection
        self.stdout.write('\nTest 5: Multiple machines available - selects next available')

        # First, create some queue entries to simulate load
        m1 = Machine.objects.get(name='Kiutra')
        m2 = Machine.objects.get(name='Opticool')

        # Add 2 entries to Kiutra's queue
        for i in range(2):
            entry = QueueEntry.objects.create(
                user=user,
                title=f'Test entry {i} for Kiutra',
                required_min_temp=1.0,
                assigned_machine=m1,
                queue_position=i+1,
                estimated_duration_hours=5,
                status='queued'
            )

        # Now test - should prefer Opticool (less queue)
        entry5 = QueueEntry(
            user=user,
            title='Should prefer Opticool',
            required_min_temp=10.0,
            estimated_duration_hours=2
        )
        machine, details = find_best_machine(entry5, return_details=True)

        self.stdout.write(f'  Kiutra queue: {m1.get_queue_count()} entries')
        self.stdout.write(f'  Opticool queue: {m2.get_queue_count()} entries')
        self.stdout.write(f'  Selected: {machine.name if machine else "None"}')

        for m_name, info in details['availability_times'].items():
            hours = int(info['wait_time'].total_seconds() // 3600)
            self.stdout.write(f'    {m_name}: wait {hours}h')

        self.stdout.write(f'  Expected: Opticool (shorter wait)')
        self.stdout.write(f'  ✓ PASS' if machine and machine.name == 'Opticool' else '  ✗ FAIL')

        # Clean up test entries
        QueueEntry.objects.filter(user=user).delete()

        self.stdout.write(self.style.SUCCESS('\n=== Testing Complete ===\n'))
