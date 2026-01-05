"""
Management command to repair queue integrity across all machines.

Usage:
    python manage.py repair_queue
    python manage.py repair_queue --machine-id 1
    python manage.py repair_queue --dry-run
"""
from django.core.management.base import BaseCommand
from calendarEditor.models import Machine, QueueEntry
from calendarEditor.matching_algorithm import reorder_queue


class Command(BaseCommand):
    help = 'Repair queue positions by removing gaps and fixing NULL positions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--machine-id',
            type=int,
            help='Repair queue for specific machine ID only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )
        parser.add_argument(
            '--no-notify',
            action='store_true',
            help='Skip user notifications about position changes',
        )

    def handle(self, *args, **options):
        machine_id = options.get('machine_id')
        dry_run = options.get('dry_run')
        notify = not options.get('no_notify')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Get machines to repair
        if machine_id:
            try:
                machines = [Machine.objects.get(id=machine_id)]
                self.stdout.write(f'Repairing queue for machine: {machines[0].name}')
            except Machine.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Machine with ID {machine_id} not found'))
                return
        else:
            machines = Machine.objects.all()
            self.stdout.write(f'Repairing queues for all {machines.count()} machines...\n')

        total_fixed = 0
        total_entries = 0

        for machine in machines:
            # Get queued entries
            queued_entries = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued'
            ).order_by('queue_position', 'submitted_at')

            if not queued_entries.exists():
                continue

            # Check for issues
            expected_positions = list(range(1, queued_entries.count() + 1))
            actual_positions = [e.queue_position for e in queued_entries]
            has_nulls = None in actual_positions
            has_gaps = actual_positions != expected_positions

            if has_nulls or has_gaps:
                total_entries += queued_entries.count()

                self.stdout.write(f'\n{machine.name}:')
                self.stdout.write(f'  Current positions: {actual_positions}')
                self.stdout.write(f'  Expected positions: {expected_positions}')

                if has_nulls:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Found NULL positions'))
                if has_gaps:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Found gaps in queue'))

                if not dry_run:
                    # Repair the queue
                    reorder_queue(machine, notify=notify)
                    total_fixed += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Repaired'))
                else:
                    total_fixed += 1
                    self.stdout.write(self.style.WARNING(f'  🔧 Would be repaired'))

        # Summary
        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN COMPLETE'))
            self.stdout.write(f'Would repair {total_fixed} machine queues affecting {total_entries} entries')
        else:
            self.stdout.write(self.style.SUCCESS(f'REPAIR COMPLETE'))
            self.stdout.write(f'Repaired {total_fixed} machine queues affecting {total_entries} entries')

        if total_fixed == 0:
            self.stdout.write(self.style.SUCCESS('✅ No issues found - all queues are healthy!'))
