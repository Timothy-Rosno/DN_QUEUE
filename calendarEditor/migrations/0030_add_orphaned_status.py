# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendarEditor', '0029_archivedmeasurement_machine_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='archivedmeasurement',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('published', 'Published'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('archived', 'Archived'),
                    ('orphaned', 'Orphaned (Machine Deleted)'),
                ],
                default='published',
                help_text='Archive entry status',
                max_length=20
            ),
        ),
    ]
