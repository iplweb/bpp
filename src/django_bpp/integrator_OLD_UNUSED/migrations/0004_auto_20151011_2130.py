# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
from django.db.migrations.operations.special import RunSQL


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('integrator2', '0003_auto_20150824_2354'),
    ]

    operations = [
        RunSQL("CREATE OR REPLACE RULE bpp_autorzy_delete AS ON DELETE TO bpp_autorzy DO INSTEAD NOTHING",
               reverse_sql="DROP RULE bpp_autorzy_delete"),
        migrations.CreateModel(
            name='IntegrationFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, verbose_name=b'Nazwa')),
                ('file', models.FileField(upload_to=b'integrator2', verbose_name=b'Plik')),
                ('type', models.IntegerField(default=0, verbose_name=b'Rodzaj', choices=[(0, b'lista DOI'), (1, b'lista AtoZ'), (2, b'integracja autor\xc3\xb3w')])),
                ('uploaded_on', models.DateTimeField(auto_now_add=True)),
                ('last_updated_on', models.DateTimeField(auto_now=True, auto_now_add=True)),
                ('status', models.IntegerField(default=0, choices=[(0, b'dodany'), (1, b'w trakcie analizy'), (2, b'przetworzony'), (3, b'przetworzony z b\xc5\x82\xc4\x99dami')])),
                ('extra_info', models.TextField()),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-last_updated_on'],
                'verbose_name': 'Plik integracji autor\xf3w',
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='autorintegrationfile',
            name='owner',
        ),
        migrations.AlterField(
            model_name='autorintegrationrecord',
            name='parent',
            field=models.ForeignKey(to='integrator2.IntegrationFile'),
            preserve_default=True,
        ),
        migrations.DeleteModel(
            name='AutorIntegrationFile',
        ),
    ]
