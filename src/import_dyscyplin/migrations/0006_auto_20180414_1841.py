# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-04-14 16:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('import_dyscyplin', '0005_auto_20180414_1801'),
    ]

    operations = [
        migrations.AddField(
            model_name='import_dyscyplin_row',
            name='info',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='import_dyscyplin_row',
            name='stan',
            field=models.CharField(choices=[('nowy', 'nowy'), ('błędny', 'błędny'), ('zintegrowany', 'zintegrowany')], default='nowy', max_length=50),
        ),
    ]
