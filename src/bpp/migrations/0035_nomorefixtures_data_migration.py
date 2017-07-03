# -*- coding: utf-8 -*-


from django.db import models, migrations

from django.core.management import call_command
from django.db.utils import IntegrityError
from django.db.migrations.operations.special import RunPython


def load_fixtures(apps, schema_editor):
    for fixture in [
        "charakter_formalny.json",
        "funkcja_autora.json",
        "jezyk.json",
        "plec.json",
        "rodzaj_zrodla.json",
        "status_korekty.json",
        # 2017/02/06 przesuwam wczytywanie tego pliku do migracji 0067 - tabela Typ_KBN została zmieniona
        # (ma więcej kolumn), wczytywanie danych przez loaddata _zawiedzie_ ponieważ loaddata używa świeżych
        # obiektów, a nie obiektów na tym etapie migracji. Zatem, w migracji 0067 sprawdzamy, czy tabela
        # Typ_KBN jest pusta, jeżeli jest - to tam zostanie zaczytany typ_kbn.json
        #
        # A tak między nami, to na tym etapie, ta migracja uruchamiana jest wyłącznie podczas testowania bazy
        # danych czy tworzenia jej od zera. Na produkcyjnej bazie danych nie zostanie uruchomiona już nigdy.
        #
        # "typ_kbn.json",
        "typ_odpowiedzialnosci.json",
        "tytul.json",
        # "um_lublin_uczelnia.json",
        # "um_lublin_wydzial.json",
        "zrodlo_informacji.json"]:
        call_command('loaddata', fixture, app='bpp', verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0034_auto_20151011_1514'),
    ]

    operations = [
        RunPython(load_fixtures)
    ]
