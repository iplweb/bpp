# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0034_auto_20151011_1514'),
        ('integrator2', '0004_auto_20151011_2130'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZrodloIntegrationRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('zanalizowano', models.BooleanField(default=False)),
                ('moze_byc_zintegrowany_automatycznie', models.BooleanField(default=False)),
                ('zintegrowano', models.BooleanField(default=False)),
                ('extra_info', models.TextField()),
                ('title', models.TextField()),
                ('www', models.TextField()),
                ('publisher', models.TextField()),
                ('issn', models.TextField()),
                ('e_issn', models.TextField()),
                ('license', models.TextField()),
                ('matching_zrodlo', models.ForeignKey(to='bpp.Zrodlo', null=True)),
                ('parent', models.ForeignKey(to='integrator2.IntegrationFile')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
