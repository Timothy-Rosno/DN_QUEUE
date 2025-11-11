"""
Management command to load initial data from fixture if database is empty.
This is used during Render deployment to populate the database.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
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
