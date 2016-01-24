# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0035_nomorefixtures_data_migration'),
        ('integrator2', '0006_auto_20151202_2204'),
    ]

    operations = [
        migrations.CreateModel(
            name='ListaMinisterialnaIntegrationRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('zanalizowano', models.BooleanField(default=False)),
                ('moze_byc_zintegrowany_automatycznie', models.BooleanField(default=False)),
                ('zintegrowano', models.BooleanField(default=False)),
                ('extra_info', models.TextField()),
                ('nazwa', models.TextField()),
                ('issn', models.TextField()),
                ('e_issn', models.TextField()),
                ('matching_zrodlo', models.ForeignKey(to='bpp.Zrodlo', null=True)),
                ('parent', models.ForeignKey(to='integrator2.IntegrationFile')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='integrationfile',
            name='param_1',
            field=models.IntegerField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='integrationfile',
            name='type',
            field=models.IntegerField(default=0, verbose_name=b'Rodzaj', choices=[(0, b'lista DOI'), (1, b'lista AtoZ'), (2, b'integracja autor\xc3\xb3w'), (3, b'integracja autor\xc3\xb3w bez PBN ID'), (4, b'import punkt\xc3\xb3w z list ministerialnych')]),
            preserve_default=True,
        ),
    ]
