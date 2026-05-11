from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("calendarEditor", "0047_queueentry_requires_temp_dependence_and_more"),
    ]

    operations = [
        # Create TrainingUpdateRequest model
        migrations.CreateModel(
            name="TrainingUpdateRequest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "training_type",
                    models.CharField(
                        choices=[("ln2", "Liquid Nitrogen"), ("quantify", "Quantify")],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resolved_training_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="training_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        # Add notify_training_request to NotificationPreference
        migrations.RunSQL(
            sql='ALTER TABLE "calendarEditor_notificationpreference" ADD COLUMN "notify_training_request" bool NOT NULL DEFAULT 1;',
            reverse_sql='ALTER TABLE "calendarEditor_notificationpreference" DROP COLUMN "notify_training_request";',
            state_operations=[
                migrations.AddField(
                    model_name="notificationpreference",
                    name="notify_training_request",
                    field=models.BooleanField(
                        default=True,
                        help_text="[Lab Manager] Notify when users request training status updates - CRITICAL",
                    ),
                ),
            ],
        ),
    ]
