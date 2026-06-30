import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DemoImport",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                        editable=False,
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("started_on", models.DateTimeField(blank=True, null=True)),
                ("finished_on", models.DateTimeField(blank=True, null=True)),
                ("finished_successfully", models.BooleanField(default=False)),
                ("cancel_requested", models.BooleanField(default=False)),
                ("cancelled", models.BooleanField(default=False)),
                ("traceback", models.TextField(blank=True, null=True)),
                ("result_context", models.JSONField(blank=True, null=True)),
                (
                    "status_text",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("percent", models.PositiveSmallIntegerField(default=0)),
                ("log", models.JSONField(default=list)),
                ("log_seq", models.PositiveIntegerField(default=0)),
                ("current_stage", models.IntegerField(default=-1)),
                ("stage_states", models.JSONField(default=dict)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_on"],
                "abstract": False,
            },
        ),
    ]
