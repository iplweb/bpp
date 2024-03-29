# Generated by Django 3.0.14 on 2021-08-08 21:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0021_auto_20210808_1204"),
        ("bpp", "0281_auto_20210725_2332"),
    ]

    operations = [
        migrations.AddField(
            model_name="konferencja",
            name="pbn_uid",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="pbn_api.Conference",
                verbose_name="Odpowiednik w PBN",
            ),
        ),
    ]
