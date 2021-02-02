# Generated by Django 3.0.11 on 2021-01-25 22:30

from django.db import migrations, models

import bpp.models.uczelnia


class Migration(migrations.Migration):

    dependencies = [
        ("raport_slotow", "0005_auto_20210125_0256"),
    ]

    operations = [
        migrations.AlterField(
            model_name="raportslotowuczelnia",
            name="do_roku",
            field=models.IntegerField(
                default=bpp.models.uczelnia.UczelniaManager.do_roku_default
            ),
        ),
        migrations.AlterField(
            model_name="raportslotowuczelniawiersz",
            name="avg",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=8,
                null=True,
                verbose_name="Średnio punktów dla autora na slot",
            ),
        ),
    ]