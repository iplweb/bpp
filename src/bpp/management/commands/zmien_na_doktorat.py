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
    Praca_Doktorska,
    cache,
)


class Command(BaseCommand):
    help = "Zmienia podany charakter wydawnictwa zwartego w doktorat"

    def add_arguments(self, parser):
        parser.add_argument("skrot")

    @transaction.atomic
    def handle(self, skrot, *args, **options):
        if cache.enabled():
            cache.disable()

        flds = Wydawnictwo_Zwarte_Baza._meta.get_fields()
        flds = [fld.name for fld in flds]
        for elem in Wydawnictwo_Zwarte.objects.filter(charakter_formalny__skrot=skrot):

            target_kw = {}
            for fld in flds:
                target_kw[fld] = getattr(elem, fld)

            assert elem.autorzy_set.all().count() == 1

            target_kw["autor"] = elem.autorzy_set.first().autor
            target_kw["jednostka"] = elem.autorzy_set.first().jednostka

            if Praca_Doktorska.objects.filter(autor=target_kw["autor"]):
                print(
                    f"*** nie tworze {target_kw['tytul_oryginalny']} bo juz istnieje!'"
                )
                continue

            Praca_Doktorska.objects.create(**target_kw)
            elem.delete()
            print(target_kw["tytul_oryginalny"])

        set_seq("bpp_praca_doktorska")
