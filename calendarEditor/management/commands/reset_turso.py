"""
Management command to reset Turso database by dropping all tables.
Used before migrations to ensure clean state.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Drop all tables in Turso database to prepare for fresh migrations'

    def handle(self, *args, **options):
        self.stdout.write("[RESET] Resetting Turso database...")

        with connection.cursor() as cursor:
            # Get all objects (tables, indexes, views, triggers)
            cursor.execute("""
                SELECT name, type FROM sqlite_master
                WHERE type IN ('table', 'index', 'view', 'trigger')
                AND name NOT LIKE 'sqlite_%'
            """)
            objects = cursor.fetchall()

            if not objects:
                self.stdout.write(self.style.SUCCESS("[OK] Database is already empty"))
                return

            # Separate by type
            indexes = [obj[0] for obj in objects if obj[1] == 'index']
            views = [obj[0] for obj in objects if obj[1] == 'view']
            triggers = [obj[0] for obj in objects if obj[1] == 'trigger']
            tables = [obj[0] for obj in objects if obj[1] == 'table']

            total = len(objects)
            self.stdout.write(f"   Found {total} objects:")
            if indexes:
                self.stdout.write(f"     - {len(indexes)} indexes")
            if views:
                self.stdout.write(f"     - {len(views)} views")
            if triggers:
                self.stdout.write(f"     - {len(triggers)} triggers")
            if tables:
                self.stdout.write(f"     - {len(tables)} tables")

            # Disable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = OFF")

            # Drop in order: indexes, views, triggers, then tables
            for idx in indexes:
                self.stdout.write(f"   Dropping index {idx}...")
                cursor.execute(f'DROP INDEX IF EXISTS "{idx}"')

            for view in views:
                self.stdout.write(f"   Dropping view {view}...")
                cursor.execute(f'DROP VIEW IF EXISTS "{view}"')

            for trigger in triggers:
                self.stdout.write(f"   Dropping trigger {trigger}...")
                cursor.execute(f'DROP TRIGGER IF EXISTS "{trigger}"')

            for table in tables:
                self.stdout.write(f"   Dropping table {table}...")
                cursor.execute(f'DROP TABLE IF EXISTS "{table}"')

            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")

            self.stdout.write(self.style.SUCCESS(f"[OK] Dropped {total} objects successfully"))
            self.stdout.write("   Ready for migrations!")
