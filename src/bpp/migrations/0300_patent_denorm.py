# Generated by Django 3.0.14 on 2021-10-03 18:23

from django.db import migrations, models

import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0299_wydawnictwo_ciagle_denorm"),
    ]

    operations = [
        migrations.AddField(
            model_name="patent",
            name="cached_punkty_dyscyplin",
            field=django.contrib.postgres.fields.jsonb.JSONField(
                blank=True, editable=False, null=True
            ),
        ),
        migrations.AlterField(
            model_name="patent",
            name="opis_bibliograficzny_autorzy_cache",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(),
                blank=True,
                editable=False,
                null=True,
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="patent",
            name="opis_bibliograficzny_cache",
            field=models.TextField(default="", editable=False),
        ),
        migrations.AlterField(
            model_name="patent",
            name="opis_bibliograficzny_zapisani_autorzy_cache",
            field=models.TextField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="patent",
            name="slug",
            field=models.SlugField(
                blank=True, editable=False, max_length=400, null=True, unique=True
            ),
        ),
    ]