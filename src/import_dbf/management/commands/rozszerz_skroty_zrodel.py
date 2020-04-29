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
            for row in list(sheet.rows):
                skrot = row[0].value
                nazwa = row[1].value
                # poprzednia_nazwa = row[2].value
                try:
                    issn = row[2].value
                except IndexError:
                    issn = None

                try:
                    e_issn = row[3].value
                except IndexError:
                    e_issn = None

                if skrot is None or nazwa is None:
                    print(
                        f"Niepoprawna linia: {[x.value for x in row]}, skrot lub nazwa sa puste"
                    )
                    continue

                try:
                    z = Zrodlo.objects.get(skrot=skrot)
                except Zrodlo.DoesNotExist:
                    print(f"Nie ma takiego zrodla jak {skrot}")
                    continue

                needs_saving = []
                if z.nazwa != nazwa:
                    z.nazwa = nazwa
                    needs_saving.append("nazwa")

                if issn is not None and z.issn != str(issn):
                    z.issn = issn
                    needs_saving.append("issn")

                if e_issn is not None and z.e_issn != str(e_issn):
                    z.e_issn = e_issn
                    needs_saving.append("e_issn")

                # if (
                #     poprzednia_nazwa is not None
                #     and z.poprzednia_nazwa != poprzednia_nazwa
                # ):
                #     z.poprzednia_nazwa = poprzednia_nazwa
                #     needs_saving.append("poprzednia")

                if needs_saving:
                    print(f"zmieniam {z.nazwa, z.pk} bo {needs_saving}")
                    z.save()
