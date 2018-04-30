# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-04-16 08:51
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


def domyslne_bazy(apps, schema_editor):
    Zewnetrzna_Baza_Danych = apps.get_model("bpp", "Zewnetrzna_Baza_Danych")
    for nazwa, skrot in [
        ("Web of Science", "WOS"),
        ("Scopus", "SCOPUS")]:
        Zewnetrzna_Baza_Danych.objects.create(
            nazwa=nazwa, skrot=skrot
        )


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0125_auto_20180415_2223'),
    ]

    operations = [
        migrations.CreateModel(
            name='Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('info', models.CharField(blank=True, max_length=512, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Zewnetrzna_Baza_Danych',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazwa', models.CharField(max_length=512, unique=True)),
                ('skrot', models.CharField(max_length=128, unique=True)),
            ],
            options={
                'verbose_name': 'zewnętrzna baza danych',
                'verbose_name_plural': 'zenwętrzne bazy danych',
                'ordering': ['nazwa'],
            },
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle_zewnetrzna_baza_danych',
            name='baza',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bpp.Zewnetrzna_Baza_Danych'),
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle_zewnetrzna_baza_danych',
            name='rekord',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bpp.Wydawnictwo_Ciagle'),
        ),

        migrations.RunPython(
            domyslne_bazy,
            migrations.RunPython.noop
        )
    ]