from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("userRegistration", "0011_userprofile_last_login_browser_and_more"),
    ]

    operations = [
        # Lab Manager fields
        migrations.RunSQL(
            sql='ALTER TABLE "userRegistration_userprofile" ADD COLUMN "is_lab_manager" bool NOT NULL DEFAULT 0;',
            reverse_sql='ALTER TABLE "userRegistration_userprofile" DROP COLUMN "is_lab_manager";',
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="is_lab_manager",
                    field=models.BooleanField(
                        default=False,
                        help_text="Has lab manager access to training management",
                    ),
                ),
            ],
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "userRegistration_userprofile" ADD COLUMN "lab_manager_promoted_by_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;',
            reverse_sql='ALTER TABLE "userRegistration_userprofile" DROP COLUMN "lab_manager_promoted_by_id";',
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="lab_manager_promoted_by",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promoted_lab_managers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "userRegistration_userprofile" ADD COLUMN "lab_manager_promoted_at" datetime NULL;',
            reverse_sql='ALTER TABLE "userRegistration_userprofile" DROP COLUMN "lab_manager_promoted_at";',
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="lab_manager_promoted_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
        # Training status fields
        migrations.RunSQL(
            sql='ALTER TABLE "userRegistration_userprofile" ADD COLUMN "ln2_trained" bool NOT NULL DEFAULT 0;',
            reverse_sql='ALTER TABLE "userRegistration_userprofile" DROP COLUMN "ln2_trained";',
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="ln2_trained",
                    field=models.BooleanField(
                        default=False,
                        help_text="Liquid Nitrogen training completed",
                    ),
                ),
            ],
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "userRegistration_userprofile" ADD COLUMN "ln2_training_date" datetime NULL;',
            reverse_sql='ALTER TABLE "userRegistration_userprofile" DROP COLUMN "ln2_training_date";',
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="ln2_training_date",
                    field=models.DateTimeField(
                        blank=True,
                        null=True,
                        help_text="Date LN2 training was last updated",
                    ),
                ),
            ],
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "userRegistration_userprofile" ADD COLUMN "quantify_trained" bool NOT NULL DEFAULT 0;',
            reverse_sql='ALTER TABLE "userRegistration_userprofile" DROP COLUMN "quantify_trained";',
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="quantify_trained",
                    field=models.BooleanField(
                        default=False,
                        help_text="Quantify training completed",
                    ),
                ),
            ],
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "userRegistration_userprofile" ADD COLUMN "quantify_training_date" datetime NULL;',
            reverse_sql='ALTER TABLE "userRegistration_userprofile" DROP COLUMN "quantify_training_date";',
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="quantify_training_date",
                    field=models.DateTimeField(
                        blank=True,
                        null=True,
                        help_text="Date Quantify training was last updated",
                    ),
                ),
            ],
        ),
    ]
