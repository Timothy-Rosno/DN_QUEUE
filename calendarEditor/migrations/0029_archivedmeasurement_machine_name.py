# Generated migration for ArchivedMeasurement machine_name field and FK change

from django.db import migrations, models
import django.db.models.deletion


def populate_machine_names(apps, schema_editor):
    """Populate machine_name from existing machine FK for all archived measurements."""
    ArchivedMeasurement = apps.get_model('calendarEditor', 'ArchivedMeasurement')

    for archive in ArchivedMeasurement.objects.all():
        if archive.machine:
            archive.machine_name = archive.machine.name
            archive.save(update_fields=['machine_name'])


def reverse_populate_machine_names(apps, schema_editor):
    """Reverse migration - no-op since we can't restore FK from name."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('calendarEditor', '0028_add_reminder_tracking'),
    ]

    operations = [
        # Add machine_name field
        migrations.AddField(
            model_name='archivedmeasurement',
            name='machine_name',
            field=models.CharField(blank=True, help_text='Machine name (preserved if machine is deleted)', max_length=100),
        ),
        # Populate machine_name from existing machine FK
        migrations.RunPython(populate_machine_names, reverse_populate_machine_names),
        # Change machine FK to SET_NULL
        migrations.AlterField(
            model_name='archivedmeasurement',
            name='machine',
            field=models.ForeignKey(
                blank=True,
                help_text='Machine used for this measurement',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='archived_measurements',
                to='calendarEditor.machine'
            ),
        ),
    ]
