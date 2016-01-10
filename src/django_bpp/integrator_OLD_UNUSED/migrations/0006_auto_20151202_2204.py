# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('integrator2', '0005_zrodlointegrationrecord'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integrationfile',
            name='type',
            field=models.IntegerField(default=0, verbose_name=b'Rodzaj', choices=[(0, b'lista DOI'), (1, b'lista AtoZ'), (2, b'integracja autor\xc3\xb3w'), (3, b'integracja autor\xc3\xb3w bez PBN ID')]),
            preserve_default=True,
        ),
    ]
