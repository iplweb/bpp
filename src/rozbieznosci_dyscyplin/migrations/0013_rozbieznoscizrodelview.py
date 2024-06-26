# Generated by Django 3.0.14 on 2021-11-03 00:04

from django.db import migrations, models

import bpp.models.cache


class Migration(migrations.Migration):

    dependencies = [
        ("rozbieznosci_dyscyplin", "0012_rozbieznosci_dyscyplin_zrodel"),
    ]

    operations = [
        migrations.CreateModel(
            name="RozbieznosciZrodelView",
            fields=[
                (
                    "id",
                    bpp.models.cache.TupleField(
                        base_field=models.IntegerField(),
                        primary_key=True,
                        serialize=False,
                        size=4,
                    ),
                ),
            ],
            options={
                "verbose_name": "rozbieżność dyscyplin źródeł",
                "verbose_name_plural": "rozbieżności dyscyplin źródeł",
                "managed": False,
            },
        ),
    ]
