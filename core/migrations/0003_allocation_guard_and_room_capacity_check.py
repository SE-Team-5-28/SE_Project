import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F


def backfill_active_student_guards(apps, schema_editor):
    Allocation = apps.get_model("core", "Allocation")
    Allocation.objects.using(schema_editor.connection.alias).filter(
        is_active=True,
    ).update(active_student_guard_id=F("student_id"))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_student_user_auditlog_hostel_block_room_allocation_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Complaint",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "reference",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("category", models.CharField(max_length=100)),
                ("description", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OPEN", "Open"),
                            ("IN_PROGRESS", "In Progress"),
                            ("RESOLVED", "Resolved"),
                            ("CLOSED", "Closed"),
                        ],
                        default="OPEN",
                        max_length=12,
                    ),
                ),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="complaints",
                        to="core.student",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="allocation",
            name="active_student_guard",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core.student",
            ),
        ),
        migrations.RunPython(
            backfill_active_student_guards,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="room",
            constraint=models.CheckConstraint(
                condition=models.Q(("capacity__gte", 1)),
                name="room_capacity_at_least_one",
            ),
        ),
    ]
