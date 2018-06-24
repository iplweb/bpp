# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-06-12 22:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0136_ranking_liczba_cytowan'),
    ]

    operations = [
        migrations.AlterField(
            model_name='praca_doktorska',
            name='liczba_cytowan',
            field=models.PositiveIntegerField(blank=True, help_text="Wartość aktualizowana jest automatycznie raz na kilka dni w przypadku \n        skonfigurowania dostępu do API WOS AMR (przez obiekt 'Uczelnia'). Możesz również\n        czaktualizować tą wartość ręcznie, naciskając przycisk. ", null=True, verbose_name='Liczba cytowań'),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='liczba_cytowan',
            field=models.PositiveIntegerField(blank=True, help_text="Wartość aktualizowana jest automatycznie raz na kilka dni w przypadku \n        skonfigurowania dostępu do API WOS AMR (przez obiekt 'Uczelnia'). Możesz również\n        czaktualizować tą wartość ręcznie, naciskając przycisk. ", null=True, verbose_name='Liczba cytowań'),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='liczba_cytowan',
            field=models.PositiveIntegerField(blank=True, help_text="Wartość aktualizowana jest automatycznie raz na kilka dni w przypadku \n        skonfigurowania dostępu do API WOS AMR (przez obiekt 'Uczelnia'). Możesz również\n        czaktualizować tą wartość ręcznie, naciskając przycisk. ", null=True, verbose_name='Liczba cytowań'),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='liczba_cytowan',
            field=models.PositiveIntegerField(blank=True, help_text="Wartość aktualizowana jest automatycznie raz na kilka dni w przypadku \n        skonfigurowania dostępu do API WOS AMR (przez obiekt 'Uczelnia'). Możesz również\n        czaktualizować tą wartość ręcznie, naciskając przycisk. ", null=True, verbose_name='Liczba cytowań'),
        ),
    ]