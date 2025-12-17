"""
NUCLEAR OPTION: Delete EVERYTHING from Turso until database is empty.
Loops multiple times to handle dependencies.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'NUKE everything from Turso database - brute force approach'

    def handle(self, *args, **options):
        self.stdout.write("[NUKE] Starting nuclear deletion...")

        max_passes = 10
        for pass_num in range(1, max_passes + 1):
            self.stdout.write(f"\n[PASS {pass_num}] Checking for objects...")

            with connection.cursor() as cursor:
                # Get ALL objects
                cursor.execute("""
                    SELECT name, type FROM sqlite_master
                    WHERE name NOT LIKE 'sqlite_%'
                    ORDER BY type DESC
                """)
                objects = cursor.fetchall()

                if not objects:
                    self.stdout.write(self.style.SUCCESS(f"[OK] Database is EMPTY after {pass_num - 1} passes"))
                    return

                self.stdout.write(f"   Found {len(objects)} objects")

                # Disable constraints
                try:
                    cursor.execute("PRAGMA foreign_keys = OFF")
                except:
                    pass

                # Try to drop each object
                dropped = 0
                for name, obj_type in objects:
                    try:
                        if obj_type == 'table':
                            cursor.execute(f'DROP TABLE IF EXISTS "{name}"')
                            self.stdout.write(f"   [DROP] Table: {name}")
                            dropped += 1
                        elif obj_type == 'index':
                            cursor.execute(f'DROP INDEX IF EXISTS "{name}"')
                            self.stdout.write(f"   [DROP] Index: {name}")
                            dropped += 1
                        elif obj_type == 'view':
                            cursor.execute(f'DROP VIEW IF EXISTS "{name}"')
                            self.stdout.write(f"   [DROP] View: {name}")
                            dropped += 1
                        elif obj_type == 'trigger':
                            cursor.execute(f'DROP TRIGGER IF EXISTS "{name}"')
                            self.stdout.write(f"   [DROP] Trigger: {name}")
                            dropped += 1
                    except Exception as e:
                        self.stdout.write(f"   [SKIP] {obj_type} {name}: {e}")

                self.stdout.write(f"   Dropped {dropped}/{len(objects)} objects")

        self.stdout.write(self.style.ERROR(f"[FAIL] Still have objects after {max_passes} passes!"))
        self.stdout.write("   You may need to manually clear the database.")
        raise SystemExit(1)  # Exit with error code so migrations don't run
