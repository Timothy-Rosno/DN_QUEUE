"""
Management command to fix corrupted queue positions.

Usage:
    python manage.py fix_queue_positions

This command:
1. Finds all machines with queued entries
2. Reorders each machine's queue to ensure sequential positions
3. Fixes any entries with NULL positions
4. Recalculates estimated start times
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from calendarEditor.models import Machine, QueueEntry
from calendarEditor.matching_algorithm import reorder_queue


class Command(BaseCommand):
    help = 'Fix corrupted queue positions and ensure all queues are properly ordered'

    def add_arguments(self, parser):
        parser.add_argument(
            '--machine',
            type=str,
            help='Specific machine name to fix (default: all machines)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )

    def handle(self, *args, **options):
        machine_name = options.get('machine')
        dry_run = options.get('dry_run')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Get machines to process
        if machine_name:
            machines = Machine.objects.filter(name=machine_name)
            if not machines.exists():
                self.stdout.write(self.style.ERROR(f'Machine "{machine_name}" not found'))
                return
        else:
            # Get all machines that have queued entries
            machines = Machine.objects.filter(
                queue_entries__status='queued'
            ).distinct()

        if not machines.exists():
            self.stdout.write(self.style.SUCCESS('No machines with queued entries found'))
            return

        self.stdout.write(f'Processing {machines.count()} machine(s)...\n')

        total_fixed = 0
        total_entries = 0

        for machine in machines:
            # Get queued entries for this machine
            queued_entries = QueueEntry.objects.filter(
                assigned_machine=machine,
                status='queued'
            ).order_by('queue_position', 'submitted_at')

            if not queued_entries.exists():
                continue

            self.stdout.write(f'\n{machine.name}:')
            self.stdout.write(f'  Found {queued_entries.count()} queued entries')

            # Check for issues
            issues = []
            positions = []
            null_positions = 0

            for entry in queued_entries:
                if entry.queue_position is None:
                    null_positions += 1
                else:
                    positions.append(entry.queue_position)

            if null_positions > 0:
                issues.append(f'{null_positions} entries with NULL position')

            # Check for gaps or duplicates
            if positions:
                expected_positions = set(range(1, len(positions) + 1))
                actual_positions = set(positions)
                if expected_positions != actual_positions:
                    missing = expected_positions - actual_positions
                    duplicates = len(positions) - len(actual_positions)
                    if missing:
                        issues.append(f'Missing positions: {sorted(missing)}')
                    if duplicates > 0:
                        issues.append(f'{duplicates} duplicate position(s)')

            if issues:
                self.stdout.write(self.style.WARNING(f'  Issues found:'))
                for issue in issues:
                    self.stdout.write(self.style.WARNING(f'    - {issue}'))
                total_fixed += 1
            else:
                self.stdout.write(self.style.SUCCESS(f'  Queue is properly ordered'))

            total_entries += queued_entries.count()

            # Fix the queue
            if not dry_run:
                if issues:
                    self.stdout.write(f'  Reordering queue...')
                    reorder_queue(machine)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Queue fixed'))

        # Summary
        self.stdout.write('\n' + '='*50)
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would fix {total_fixed} machine(s) with {total_entries} total entries'))
        else:
            if total_fixed > 0:
                self.stdout.write(self.style.SUCCESS(f'✓ Fixed {total_fixed} machine(s) with {total_entries} total entries'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ All queues are properly ordered'))
