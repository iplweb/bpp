# Generated by Django 3.2.14 on 2022-07-07 22:32

from django.db import migrations, models

import django.contrib.postgres.fields

import bpp.models.uczelnia


class Migration(migrations.Migration):

    dependencies = [
        ("raport_slotow", "0011_auto_20210315_0141"),
    ]

    operations = [
        migrations.CreateModel(
            name="RaportEwaluacjaUpowaznieniaView",
            fields=[
                (
                    "id",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.PositiveIntegerField(),
                        primary_key=True,
                        serialize=False,
                        size=4,
                    ),
                ),
            ],
            options={
                "db_table": "bpp_ewaluacja_upowaznienia_view",
                "managed": False,
            },
        ),
        migrations.AlterField(
            model_name="raportslotowuczelnia",
            name="do_roku",
            field=models.IntegerField(
                default=bpp.models.uczelnia.UczelniaManager.do_roku_default
            ),
        ),
    ]