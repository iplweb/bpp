# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-23 09:00
from __future__ import unicode_literals

from django.db import migrations

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0102_auto_20170723_2318'),
    ]

    operations = [
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql("0103_widoki_nowe_sumy")),

    ]
