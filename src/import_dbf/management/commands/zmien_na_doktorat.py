# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.management.commands.import_bpp import set_seq
from bpp.models import (
    Autor,
    Jednostka,
    Wydzial,
    Uczelnia,
    Zrodlo,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Baza,
    cache,
)

from bpp import models


class Command(BaseCommand):
    help = "Zmienia podany charakter wydawnictwa zwartego w doktorat"

    def add_arguments(self, parser):
        parser.add_argument("typ_kbn_nazwa")
        parser.add_argument("klasa_docelowa")

    @transaction.atomic
    def handle(self, typ_kbn_nazwa, klasa_docelowa, *args, **options):
        if cache.enabled():
            cache.disable()

        klasa_docelowa = getattr(models, klasa_docelowa)
        flds = Wydawnictwo_Zwarte_Baza._meta.get_fields()
        flds = [fld.name for fld in flds]
        for elem in Wydawnictwo_Zwarte.objects.filter(typ_kbn__nazwa=typ_kbn_nazwa):

            target_kw = {}
            for fld in flds:
                target_kw[fld] = getattr(elem, fld)

            assert elem.autorzy_set.all().count() == 1

            target_kw["autor"] = elem.autorzy_set.first().autor
            target_kw["jednostka"] = elem.autorzy_set.first().jednostka

            if klasa_docelowa.objects.filter(autor=target_kw["autor"]):
                print(
                    f"*** nie tworze {target_kw['tytul_oryginalny']} bo juz istnieje!'"
                )
                continue

            klasa_docelowa.objects.create(**target_kw)
            elem.delete()
            print(target_kw["tytul_oryginalny"])

        set_seq(klasa_docelowa._meta.db_table)
