# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.db.models import CASCADE, SET_NULL

import integrator2.models.lista_ministerialna
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bpp', '0035_nomorefixtures_data_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='ListaMinisterialnaElement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('zanalizowano', models.BooleanField(default=False)),
                ('moze_byc_zintegrowany_automatycznie', models.NullBooleanField(default=None)),
                ('extra_info', models.TextField()),
                ('zintegrowano', models.BooleanField(default=False)),
                ('nazwa', models.TextField()),
                ('issn', models.CharField(max_length=32, null=True, verbose_name='ISSN', blank=True)),
                ('e_issn', models.CharField(max_length=32, null=True, verbose_name='e-ISSN', blank=True)),
                ('punkty_kbn', models.IntegerField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ListaMinisterialnaIntegration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, verbose_name=b'Nazwa pliku')),
                ('file', models.FileField(upload_to=b'integrator2', verbose_name=b'Plik')),
                ('uploaded_on', models.DateTimeField(auto_now_add=True)),
                ('last_updated_on', models.DateTimeField(auto_now=True, auto_now_add=True)),
                ('status', models.IntegerField(default=0, choices=[(0, b'dodany'), (1, b'w trakcie analizy'), (2, b'przetworzony'), (3, b'przetworzony z b\xc5\x82\xc4\x99dami')])),
                ('extra_info', models.TextField()),
                ('year', models.IntegerField(default=integrator2.models.lista_ministerialna.last_year)),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=CASCADE)),
            ],
            options={
                'verbose_name': 'Integracja list ministerialnych',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='listaministerialnaelement',
            name='parent',
            field=models.ForeignKey(to='integrator2.ListaMinisterialnaIntegration', on_delete=CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='listaministerialnaelement',
            name='zrodlo',
            field=models.ForeignKey(blank=True, to='bpp.Zrodlo', null=True, on_delete=SET_NULL),
            preserve_default=True,
        ),
    ]
