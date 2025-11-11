"""
Management command to update machine temperature cache.
Run this in the background to keep temperatures up-to-date without blocking page loads.

Usage:
    python manage.py update_temperatures           # Run once
    python manage.py update_temperatures --loop    # Run continuously
"""
from django.core.management.base import BaseCommand
from calendarEditor.models import Machine
import time


class Command(BaseCommand):
    help = 'Update cached temperature and status for all machines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Run continuously in a loop',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Update interval in seconds (default: 5)',
        )

    def handle(self, *args, **options):
        loop = options['loop']
        interval = options['interval']

        if loop:
            self.stdout.write(self.style.SUCCESS(
                f'Starting continuous temperature updates (every {interval}s). Press Ctrl+C to stop.'
            ))
            try:
                while True:
                    self.update_all_machines()
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\nStopping temperature updates.'))
        else:
            self.update_all_machines()

    def update_all_machines(self):
        """Update temperature cache for all machines with monitoring configured."""
        machines = Machine.objects.exclude(api_type='none')

        if not machines.exists():
            self.stdout.write(self.style.WARNING('No machines configured for monitoring.'))
            return

        for machine in machines:
            try:
                machine.update_temperature_cache()

                if machine.cached_online:
                    temp_str = f"{machine.cached_temperature:.2f} K" if machine.cached_temperature else "N/A"
                    self.stdout.write(
                        f"{machine.name}: Online, Temp={temp_str}"
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"{machine.name}: Offline")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"{machine.name}: Error - {str(e)}")
                )
