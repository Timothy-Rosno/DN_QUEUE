"""
Management command to reset all PostgreSQL sequences.
Run this after a database restore to fix sequence issues.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps


class Command(BaseCommand):
    help = 'Reset all PostgreSQL sequences to prevent duplicate key errors after restore'

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stdout.write(self.style.WARNING('This command only works with PostgreSQL'))
            return

        # Get all models
        models = apps.get_models()

        reset_count = 0

        with connection.cursor() as cursor:
            for model in models:
                table_name = model._meta.db_table

                # Check if table has an id field (primary key)
                if hasattr(model, 'id'):
                    try:
                        # Reset sequence for this table
                        cursor.execute(f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table_name}', 'id'),
                                COALESCE(MAX(id), 1),
                                MAX(id) IS NOT NULL
                            )
                            FROM {table_name};
                        """)

                        result = cursor.fetchone()
                        if result:
                            new_value = result[0]
                            self.stdout.write(
                                f'Reset {table_name} sequence to {new_value}'
                            )
                            reset_count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Could not reset {table_name}: {e}')
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully reset {reset_count} sequences!'
            )
        )
