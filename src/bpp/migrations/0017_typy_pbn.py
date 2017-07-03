# -*- coding: utf-8 -*-

import os
from django.db import models, migrations
import csv

def migration_open(fn):
    p = os.path.join(
        os.path.dirname(__file__),
        fn)

    return open(p, encoding="utf-8")

def dodaj_dane_typow_pbn(apps, schema_editor):
    Charakter_PBN = apps.get_model("bpp", "Charakter_PBN")

    mapa = dict()
    for row in csv.reader(migration_open("0017_typy_pbn_map.txt")):
        for elem in row[1:]:
            mapa[elem] = row[0]

    for identyfikator, opis, help_text in csv.reader(
            migration_open("0017_typy_pbn.txt"), delimiter=';'):
        Charakter_PBN.objects.create(
            wlasciwy_dla=mapa.get(identyfikator, "article"),
            identyfikator=identyfikator,
            opis=opis,
            help_text=help_text)

class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0016_auto_20150824_1051'),
    ]

    operations = [
        migrations.CreateModel(
            name='Charakter_PBN',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('wlasciwy_dla', models.CharField(max_length=20, choices=[
                    (b'article', b'Artyku\xc5\x82'),
                    (b'book', b'Ksi\xc4\x85\xc5\xbcka'),
                    (b'chapter', b'Rozdzia\xc5\x82')])),
                ('identyfikator', models.CharField(max_length=100)),
                ('opis', models.CharField(max_length=500)),
                ('help_text', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['identyfikator'],
            },
            bases=(models.Model,),
        ),
        migrations.RunPython(dodaj_dane_typow_pbn)
    ]
