# Generated by Django 3.2.14 on 2022-07-08 11:12

from django.db import migrations, models

import bpp.models.uczelnia


class Migration(migrations.Migration):

    dependencies = [
        ("raport_slotow", "0012_django32"),
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
