# Generated by Django 3.0.14 on 2021-10-03 18:31

from django.db import migrations, models

import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0300_patent_denorm"),
    ]

    operations = [
        migrations.AlterField(
            model_name="praca_doktorska",
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
            model_name="praca_doktorska",
            name="opis_bibliograficzny_cache",
            field=models.TextField(default="", editable=False),
        ),
        migrations.AlterField(
            model_name="praca_doktorska",
            name="opis_bibliograficzny_zapisani_autorzy_cache",
            field=models.TextField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="praca_doktorska",
            name="slug",
            field=models.SlugField(
                blank=True, editable=False, max_length=400, null=True, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="praca_habilitacyjna",
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
            model_name="praca_habilitacyjna",
            name="opis_bibliograficzny_cache",
            field=models.TextField(default="", editable=False),
        ),
        migrations.AlterField(
            model_name="praca_habilitacyjna",
            name="opis_bibliograficzny_zapisani_autorzy_cache",
            field=models.TextField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="praca_habilitacyjna",
            name="slug",
            field=models.SlugField(
                blank=True, editable=False, max_length=400, null=True, unique=True
            ),
        ),
    ]
