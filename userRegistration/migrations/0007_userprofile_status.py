# Generated migration for adding status field to UserProfile

from django.db import migrations, models


def migrate_is_approved_to_status(apps, schema_editor):
    """Migrate existing is_approved values to new status field."""
    UserProfile = apps.get_model('userRegistration', 'UserProfile')

    # Migrate True -> 'approved', False -> 'pending'
    for profile in UserProfile.objects.all():
        if profile.is_approved:
            profile.status = 'approved'
        else:
            profile.status = 'pending'
        profile.save(update_fields=['status'])


def reverse_migrate_status_to_is_approved(apps, schema_editor):
    """Reverse migration: migrate status back to is_approved."""
    UserProfile = apps.get_model('userRegistration', 'UserProfile')

    # Migrate 'approved' -> True, everything else -> False
    for profile in UserProfile.objects.all():
        profile.is_approved = (profile.status == 'approved')
        profile.save(update_fields=['is_approved'])


class Migration(migrations.Migration):

    dependencies = [
        ('userRegistration', '0006_userprofile_slack_member_id_alter_userprofile_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('rejected', 'Rejected'), ('approved', 'Approved')],
                default='pending',
                help_text='User approval status',
                max_length=20
            ),
        ),
        # Migrate existing data from is_approved to status
        migrations.RunPython(migrate_is_approved_to_status, reverse_migrate_status_to_is_approved),
    ]
