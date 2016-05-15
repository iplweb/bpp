# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import integrator2.models.egeria


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0038_autor_pesel_md5'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('integrator2', '0002_auto_20160124_1336'),
    ]

    operations = [
        migrations.CreateModel(
            name='EgeriaImportElement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('zanalizowano', models.BooleanField(default=False)),
                ('moze_byc_zintegrowany_automatycznie', models.NullBooleanField(default=None)),
                ('extra_info', models.TextField()),
                ('zintegrowano', models.BooleanField(default=False)),
                ('sheet_name', models.CharField(max_length=50)),
                ('lp', models.IntegerField()),
                ('tytul_stopien', models.CharField(max_length=200)),
                ('nazwisko', models.CharField(max_length=200)),
                ('imie', models.CharField(max_length=200)),
                ('pesel_md5', models.CharField(max_length=32)),
                ('stanowisko', models.CharField(max_length=200)),
                ('nazwa_jednostki', models.CharField(max_length=512)),
                ('nazwa_wydzialu', models.CharField(max_length=512)),
                ('autor_id', models.ForeignKey(blank=True, to='bpp.Autor', null=True)),
                ('jednostka_id', models.ForeignKey(blank=True, to='bpp.Jednostka', null=True)),
            ],
            options={
                'ordering': ['sheet_name', 'lp'],
            },
        ),
        migrations.CreateModel(
            name='EgeriaImportIntegration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, verbose_name=b'Nazwa pliku')),
                ('file', models.FileField(upload_to=b'integrator2', verbose_name=b'Plik')),
                ('uploaded_on', models.DateTimeField(auto_now_add=True)),
                ('last_updated_on', models.DateTimeField(auto_now=True)),
                ('status', models.IntegerField(default=0, choices=[(0, b'dodany'), (1, b'w trakcie analizy'), (2, b'przetworzony'), (3, b'przetworzony z b\xc5\x82\xc4\x99dami')])),
                ('extra_info', models.TextField()),
                ('date', models.DateField(default=integrator2.models.egeria.today, help_text='Data wygenerowania danych w systemie Egeria', verbose_name='Data')),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-uploaded_on'],
                'verbose_name': 'integracja danych z Egeria',
            },
        ),
        migrations.CreateModel(
            name='UsunWydzial',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('parent', models.ForeignKey(to='integrator2.EgeriaImportIntegration')),
                ('wydzial', models.ForeignKey(to='bpp.Wydzial')),
            ],
        ),
        migrations.CreateModel(
            name='UtworzJednostke',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nazwa_wydzialu', models.TextField()),
                ('nazwa', models.TextField()),
                ('parent', models.ForeignKey(to='integrator2.EgeriaImportIntegration')),
            ],
        ),
        migrations.CreateModel(
            name='UtworzWydzial',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nazwa', models.TextField()),
                ('parent', models.ForeignKey(to='integrator2.EgeriaImportIntegration')),
                ('uczelnia', models.ForeignKey(to='bpp.Uczelnia', blank=True, null=True, db_index=False)),
                ('wydzial', models.ForeignKey(to='bpp.Wydzial', blank=True, null=True, db_index=False)),
            ],
        ),
        migrations.CreateModel(
            name='ZaktualizujWydzial',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('parent', models.ForeignKey(to='integrator2.EgeriaImportIntegration')),
                ('wydzial', models.ForeignKey(to='bpp.Wydzial')),
            ],
        ),
        migrations.AddField(
            model_name='egeriaimportelement',
            name='parent',
            field=models.ForeignKey(to='integrator2.EgeriaImportIntegration'),
        ),
        migrations.AddField(
            model_name='egeriaimportelement',
            name='wydzial_id',
            field=models.ForeignKey(blank=True, to='bpp.Wydzial', null=True),
        ),
    ]
