# Generated by Django 3.0.14 on 2021-07-13 20:29

import django.db.models.deletion
from django.db import migrations, models

import django.contrib.postgres.fields.jsonb


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0012_auto_20210621_0947"),
    ]

    operations = [
        migrations.CreateModel(
            name="OswiadczenieInstytucji",
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
                ("addedTimestamp", models.DateField()),
                ("area", models.PositiveSmallIntegerField()),
                ("inOrcid", models.BooleanField()),
                ("type", models.CharField(max_length=50)),
                (
                    "institutionId",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pbn_api.Institution",
                    ),
                ),
                (
                    "personId",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pbn_api.Scientist",
                    ),
                ),
                (
                    "publicationId",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pbn_api.Publication",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PublikacjaInstytucji",
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
                ("publicationType", models.CharField(max_length=50)),
                ("publicationVersion", models.UUIDField()),
                ("publicationYear", models.PositiveSmallIntegerField()),
                ("snapshot", django.contrib.postgres.fields.jsonb.JSONField()),
                (
                    "insPersonId",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pbn_api.Scientist",
                    ),
                ),
                (
                    "institutionId",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pbn_api.Institution",
                    ),
                ),
                (
                    "publicationId",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pbn_api.Publication",
                    ),
                ),
            ],
            options={
                "unique_together": {("insPersonId", "institutionId", "publicationId")},
            },
        ),
    ]
