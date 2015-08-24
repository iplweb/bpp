# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('integrator', '0002_autorintegrationfile_last_updated_on'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='autorintegrationfile',
            options={'ordering': ['-last_updated_on'], 'verbose_name': 'Plik integracji autor\xf3w'},
        ),
        migrations.AlterField(
            model_name='autorintegrationfile',
            name='status',
            field=models.IntegerField(default=0, choices=[(0, b'dodany'), (1, b'w trakcie analizy'), (2, b'przetworzony'), (3, b'przetworzony z b\xc5\x82\xc4\x99dami')]),
            preserve_default=True,
        ),
    ]
