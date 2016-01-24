# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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
        "typ_kbn.json",
        "typ_odpowiedzialnosci.json",
        "tytul.json",
        # "um_lublin_uczelnia.json",
        # "um_lublin_wydzial.json",
        "zrodlo_informacji.json"]:
        call_command('loaddata', fixture, app_label='bpp')


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0034_auto_20151011_1514'),
    ]

    operations = [
        RunPython(load_fixtures)
    ]
