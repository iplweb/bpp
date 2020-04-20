# -*- encoding: utf-8 -*-
import argparse
import logging

from django.core.management import BaseCommand
from django.db import transaction
from openpyxl import load_workbook

from bpp.models import Zrodlo, Rodzaj_Zrodla


class Command(BaseCommand):
    help = "Rozszera skroty zrodel na podstawie pliku"

    def add_arguments(self, parser):
        parser.add_argument("plik", type=argparse.FileType("rb"))

    @transaction.atomic
    def handle(self, plik, *args, **options):
        verbosity = int(options["verbosity"])
        logger = logging.getLogger("django")
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        wb = load_workbook(plik)

        for sheet in wb.worksheets:
            for row in list(sheet.rows)[1:]:
                skrot, nazwa, poprzednia_nazwa, issn, e_issn = [x.value for x in row]

                try:
                    z = Zrodlo.objects.get(skrot=skrot)
                except Zrodlo.DoesNotExist:
                    print("Tworze %s" % nazwa)
                    Zrodlo.objects.create(
                        rodzaj=Rodzaj_Zrodla.objects.get(nazwa="periodyk"),
                        skrot=skrot,
                        nazwa=nazwa,
                        poprzednia_nazwa=poprzednia_nazwa,
                        issn=issn,
                        e_issn=e_issn,
                    )
                    continue

                needs_saving = False
                if z.nazwa != nazwa:
                    z.nazwa = nazwa
                    needs_saving = True

                if z.issn != issn:
                    z.issn = issn
                    needs_saving = True

                if z.e_issn != e_issn:
                    z.e_issn = e_issn
                    needs_saving = True

                if z.poprzednia_nazwa != poprzednia_nazwa:
                    z.poprzednia_nazwa = poprzednia_nazwa
                    needs_saving = True

                if needs_saving:
                    print("zmieniam %s" % z.nazwa)
                    z.save()
