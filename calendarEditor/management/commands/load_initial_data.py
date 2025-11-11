"""
Management command to load initial data from fixture if database is empty.
This is used during Render deployment to populate the database.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from calendarEditor.models import Machine
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Load initial data from fixture if database is empty (for Render deployment)'

    def handle(self, *args, **options):
        # Check if database already has machines (indicating it's already populated)
        if Machine.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    'Database already has machines - skipping initial data load'
                )
            )
            return

        # Check if there's partial data from a failed previous deployment
        user_count = User.objects.count()
        if user_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Database has {user_count} users but no machines.\n'
                    f'This indicates a failed previous deployment.\n'
                    f'Clearing all data and reloading...'
                )
            )
            # Flush all data to start clean
            call_command('flush', '--noinput', verbosity=0)

        # Load the fixture
        self.stdout.write('Loading initial data from initial_data.json...')
        try:
            call_command('loaddata', 'initial_data.json', verbosity=2)
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Initial data loaded successfully!\n'
                    f'   Machines: {Machine.objects.count()}\n'
                    f'   Users: {User.objects.count()}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error loading initial data: {e}')
            )
            raise
