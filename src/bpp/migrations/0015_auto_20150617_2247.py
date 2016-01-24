# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from decimal import Decimal
import djorm_pgarray.fields
import django.db.models.deletion
import djorm_pgfulltext.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('bpp', '0014_auto_20150530_1942'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='zrodlo',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name=b'\xc5\xb9r\xc3\xb3d\xc5\x82o', to='bpp.Zrodlo', null=True),
            preserve_default=True,
        ),
    ]
