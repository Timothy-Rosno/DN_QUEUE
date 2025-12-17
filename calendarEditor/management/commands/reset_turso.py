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
            # Get all table names
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            if not tables:
                self.stdout.write(self.style.SUCCESS("[OK] Database is already empty"))
                return

            self.stdout.write(f"   Found {len(tables)} tables: {', '.join(tables)}")

            # Disable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = OFF")

            # Drop each table
            for table in tables:
                self.stdout.write(f"   Dropping {table}...")
                cursor.execute(f'DROP TABLE IF EXISTS "{table}"')

            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")

            self.stdout.write(self.style.SUCCESS(f"[OK] Dropped {len(tables)} tables successfully"))
            self.stdout.write("   Ready for migrations!")
