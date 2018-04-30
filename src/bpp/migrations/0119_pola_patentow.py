# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-03-05 09:53
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models

from bpp import initial


def wczytaj_rodzaje_praw(apps, schema_editor):
    Rodzaj_Prawa_Patentowego = apps.get_model("bpp", "Rodzaj_Prawa_Patentowego")
    for nazwa in initial.rodzaj_prawa_patentowego:
        Rodzaj_Prawa_Patentowego.objects.create(
            nazwa=nazwa)


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0118_auto_20180221_2335'),
    ]

    operations = [
        migrations.CreateModel(
            name='Rodzaj_Prawa_Patentowego',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazwa', models.CharField(max_length=512, unique=True)),
            ],
            options={
                'verbose_name': 'rodzaj prawa patentowego',
                'verbose_name_plural': 'rodzaje praw patentowych',
                'ordering': ['nazwa'],
            },
        ),
        migrations.RenameField(
            model_name='patent',
            old_name='z_dnia',
            new_name='data_decyzji',
        ),
        migrations.RemoveField(
            model_name='patent',
            name='numer',
        ),
        migrations.AddField(
            model_name='patent',
            name='data_zgloszenia',
            field=models.DateField(blank=True, null=True, verbose_name='Data zgłoszenia'),
        ),
        migrations.AddField(
            model_name='patent',
            name='numer_prawa_wylacznego',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Numer prawa wyłącznego'),
        ),
        migrations.AddField(
            model_name='patent',
            name='numer_zgloszenia',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Numer zgłoszenia'),
        ),
        migrations.AddField(
            model_name='patent',
            name='wdrozenie',
            field=models.NullBooleanField(verbose_name='Wdrożenie'),
        ),
        migrations.AddField(
            model_name='patent',
            name='wydzial',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to='bpp.Wydzial'),
        ),
        migrations.AddField(
            model_name='patent',
            name='rodzaj_prawa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='bpp.Rodzaj_Prawa_Patentowego'),
        ),
        migrations.RunPython(
            wczytaj_rodzaje_praw,
            migrations.RunPython.noop
        )
    ]