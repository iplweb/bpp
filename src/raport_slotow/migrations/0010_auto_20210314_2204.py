# Generated by Django 3.0.11 on 2021-03-14 21:04

from django.db import migrations, models

import bpp.models.uczelnia


class Migration(migrations.Migration):

    dependencies = [
        ("raport_slotow", "0009_auto_20210308_0846"),
    ]

    operations = [
        migrations.AlterField(
            model_name="raportslotowuczelnia",
            name="do_roku",
            field=models.IntegerField(
                default=bpp.models.uczelnia.UczelniaManager.do_roku_default
            ),
        ),
    ]