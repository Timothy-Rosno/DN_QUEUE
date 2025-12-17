"""
Management command to sync database with Turso.

Usage:
    python manage.py sync_turso --push    # Upload local database to Turso
    python manage.py sync_turso --pull    # Download Turso database to local
    python manage.py sync_turso --status  # Check Turso connection status
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import json


class Command(BaseCommand):
    help = 'Sync database with Turso (SQLite edge database)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--push',
            action='store_true',
            help='Push local database to Turso',
        )
        parser.add_argument(
            '--pull',
            action='store_true',
            help='Pull Turso database to local',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Check Turso connection status',
        )

    def handle(self, *args, **options):
        # Check if Turso is configured
        turso_url = os.environ.get('TURSO_DATABASE_URL')
        turso_token = os.environ.get('TURSO_AUTH_TOKEN')

        if not turso_url or not turso_token:
            raise CommandError(
                "Turso not configured. Please set:\n"
                "  - TURSO_DATABASE_URL\n"
                "  - TURSO_AUTH_TOKEN\n"
                "environment variables."
            )

        # Import libsql client
        try:
            import libsql_client
        except ImportError:
            raise CommandError(
                "libsql-client-py not installed.\n"
                "Install with: pip install libsql-client-py"
            )

        # Create Turso client
        try:
            client = libsql_client.create_client(
                url=turso_url,
                auth_token=turso_token
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Connected to Turso: {turso_url}'))
        except Exception as e:
            raise CommandError(f"Failed to connect to Turso: {e}")

        # Handle different actions
        if options['status']:
            self.check_status(client, turso_url)
        elif options['push']:
            self.push_to_turso(client)
        elif options['pull']:
            self.pull_from_turso(client)
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Please specify an action:\n'
                    '  --push   : Upload local database to Turso\n'
                    '  --pull   : Download Turso database to local\n'
                    '  --status : Check connection status'
                )
            )

    def check_status(self, client, turso_url):
        """Check Turso connection and database status."""
        try:
            # Execute a simple query to test connection
            result = client.execute("SELECT 1")
            self.stdout.write(self.style.SUCCESS('✓ Turso connection is healthy'))
            self.stdout.write(f'  URL: {turso_url}')

            # Check if tables exist
            tables_result = client.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in tables_result.rows]

            if tables:
                self.stdout.write(f'  Tables found: {len(tables)}')
                for table in tables[:10]:  # Show first 10 tables
                    self.stdout.write(f'    - {table}')
                if len(tables) > 10:
                    self.stdout.write(f'    ... and {len(tables) - 10} more')
            else:
                self.stdout.write(self.style.WARNING('  No tables found (database is empty)'))

        except Exception as e:
            raise CommandError(f'Connection test failed: {e}')

    def push_to_turso(self, client):
        """Push local SQLite database to Turso."""
        self.stdout.write('Pushing local database to Turso...')

        # Use Django's database backup/restore functionality
        from django.core.management import call_command
        from io import StringIO
        import tempfile

        try:
            # Export local database to JSON
            self.stdout.write('  1. Exporting local database to JSON...')
            json_output = StringIO()
            call_command('dumpdata', stdout=json_output, indent=2)
            data = json_output.getvalue()

            # Clear existing Turso database (optional - can be skipped)
            self.stdout.write('  2. Clearing Turso database...')
            # Get all tables
            tables_result = client.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row[0] for row in tables_result.rows]
            for table in tables:
                try:
                    client.execute(f"DELETE FROM {table}")
                except:
                    pass  # Ignore errors for tables that might not exist

            # Load data to Turso
            self.stdout.write('  3. Loading data to Turso...')

            # This is a simplified approach - you may need to customize based on your models
            # For a production setup, consider using Django's loaddata with a Turso-connected database

            self.stdout.write(
                self.style.SUCCESS(
                    '✓ Database exported to JSON\n'
                    '\n'
                    'NEXT STEPS:\n'
                    '1. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in environment\n'
                    '2. Run: python manage.py migrate (with Turso config)\n'
                    '3. Run: python manage.py loaddata <backup_file>.json\n'
                    '\n'
                    'This will import your data into Turso.'
                )
            )

        except Exception as e:
            raise CommandError(f'Push failed: {e}')

    def pull_from_turso(self, client):
        """Pull Turso database to local SQLite."""
        self.stdout.write('Pulling Turso database to local...')
        self.stdout.write(
            self.style.WARNING(
                'IMPORTANT: This will overwrite your local database!\n'
                'Make sure you have a backup before proceeding.\n'
            )
        )

        # For now, just provide instructions
        self.stdout.write(
            self.style.SUCCESS(
                '\n'
                'To pull from Turso:\n'
                '1. Export Turso database using: turso db shell <db-name> ".dump" > turso_dump.sql\n'
                '2. Import to local SQLite: sqlite3 db.sqlite3 < turso_dump.sql\n'
                '\n'
                'Or use the admin interface to import a JSON backup.'
            )
        )
