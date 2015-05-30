# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0014_auto_20150530_1942'),
    ]

    operations = [
        migrations.AddField(
            model_name='patent',
            name='opis_bibliograficzny_zapisani_autorzy_cache',
            field=models.TextField(default=b''),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_doktorska',
            name='opis_bibliograficzny_zapisani_autorzy_cache',
            field=models.TextField(default=b''),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='praca_habilitacyjna',
            name='opis_bibliograficzny_zapisani_autorzy_cache',
            field=models.TextField(default=b''),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_ciagle',
            name='opis_bibliograficzny_zapisani_autorzy_cache',
            field=models.TextField(default=b''),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='wydawnictwo_zwarte',
            name='opis_bibliograficzny_zapisani_autorzy_cache',
            field=models.TextField(default=b''),
            preserve_default=True,
        ),
    ]
