# Generated by Django 2.2.10 on 2020-03-08 21:04

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0201_rekord_mat_z_www"),
    ]

    operations = [
        migrations.AddField(
            model_name="cache_punktacja_dyscypliny",
            name="zapisani_autorzy_z_dyscypliny",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(), blank=True, null=True, size=None
            ),
        ),
        migrations.AddField(
            model_name="cache_punktacja_dyscypliny",
            name="zapisani_wszyscy_autorzy",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(), blank=True, null=True, size=None
            ),
        ),
    ]