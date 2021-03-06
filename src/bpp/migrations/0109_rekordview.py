# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-09-19 12:40
from __future__ import unicode_literals

import bpp.models.cache
from decimal import Decimal
import django.contrib.postgres.fields
import django.contrib.postgres.search
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0108_bpp_nowe_sumy_view_bug'),
    ]

    operations = [
        migrations.CreateModel(
            name='RekordView',
            fields=[
                ('opis_bibliograficzny_cache', models.TextField(default='')),
                ('opis_bibliograficzny_autorzy_cache', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, null=True, size=None)),
                ('opis_bibliograficzny_zapisani_autorzy_cache', models.TextField(default='')),
                ('liczba_znakow_wydawniczych', models.IntegerField(blank=True, db_index=True, null=True, verbose_name='Liczba znaków wydawniczych')),
                ('rok', models.IntegerField(db_index=True, help_text='Rok uwzględniany przy wyszukiwaniu i raportach\n        KBN/MNiSW)')),
                ('recenzowana', models.BooleanField(db_index=True, default=False)),
                ('impact_factor', models.DecimalField(db_index=True, decimal_places=3, default=Decimal('0.000'), max_digits=6)),
                ('punkty_kbn', models.DecimalField(db_index=True, decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Punkty KBN')),
                ('index_copernicus', models.DecimalField(db_index=True, decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Index Copernicus')),
                ('punktacja_wewnetrzna', models.DecimalField(db_index=True, decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Punktacja wewnętrzna')),
                ('kc_impact_factor', models.DecimalField(blank=True, db_index=True, decimal_places=2, default=None, help_text='Jeżeli wpiszesz\n        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji\n        Centralnej w punkcie IXa tego raportu.', max_digits=6, null=True, verbose_name='KC: Impact factor')),
                ('kc_punkty_kbn', models.DecimalField(blank=True, db_index=True, decimal_places=2, default=None, help_text='Jeżeli wpiszesz\n        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji\n        Centralnej w punkcie IXa i IXb tego raportu.', max_digits=6, null=True, verbose_name='KC: Punkty KBN')),
                ('kc_index_copernicus', models.DecimalField(blank=True, decimal_places=2, default=None, help_text='Jeżeli wpiszesz\n        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji\n        Centralnej w punkcie IXa i IXb tego raportu.', max_digits=6, null=True, verbose_name='KC: Index Copernicus')),
                ('informacje', models.TextField(blank=True, db_index=True, null=True, verbose_name='Informacje')),
                ('szczegoly', models.CharField(blank=True, help_text='Np. str. 23-45', max_length=512, null=True, verbose_name='Szczegóły')),
                ('uwagi', models.TextField(blank=True, db_index=True, null=True)),
                ('slowa_kluczowe', models.TextField(blank=True, null=True, verbose_name='Słowa kluczowe')),
                ('utworzono', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Utworzono')),
                ('openaccess_ilosc_miesiecy', models.PositiveIntegerField(blank=True, help_text='Ilość miesięcy jakie upłynęły od momentu opublikowania do momentu udostępnienia', null=True, verbose_name='OpenAccess: ilość miesięcy')),
                ('id', bpp.models.cache.TupleField(base_field=models.IntegerField(), primary_key=True, serialize=False, size=2)),
                ('tytul_oryginalny', models.TextField()),
                ('tytul', models.TextField()),
                ('search_index', django.contrib.postgres.search.SearchVectorField()),
                ('wydawnictwo', models.TextField()),
                ('adnotacje', models.TextField()),
                ('ostatnio_zmieniony', models.DateTimeField()),
                ('tytul_oryginalny_sort', models.TextField()),
                ('www', models.URLField(blank=True, max_length=1024, null=True, verbose_name='Adres WWW')),
            ],
            options={
                'db_table': 'bpp_rekord',
                'managed': False,
            },
        ),
    ]
