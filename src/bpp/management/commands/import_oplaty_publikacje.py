import argparse
from optparse import OptionParser

import pandas
from django.core.management import BaseCommand
from django.db import transaction

from import_common.normalization import (
    normalize_oplaty_za_publikacje,
    normalize_rekord_id,
)

from bpp.models import ModelZOplataZaPublikacje, Rekord
from bpp.util import pbar


class Command(BaseCommand):
    help = 'Import opłat za publikację wg "własnego" formatu z BPP'
    args = "<plik xls 1> <plik xls 2> ..."

    def add_arguments(self, parser: OptionParser):
        parser.add_argument("pliki", type=argparse.FileType("rb"), nargs="+")

    @transaction.atomic
    def handle(self, pliki, *args, **options):

        for plik in pbar(pliki):
            xlsx = pandas.read_excel(plik)

            for row in xlsx.iloc:
                pk = normalize_rekord_id(row[1])
                if pk is None:
                    continue

                rekord = Rekord.objects.get(pk=pk)
                original: ModelZOplataZaPublikacje = rekord.original
                assert rekord.tytul_oryginalny == row["Tytuł oryginalny"]

                normalize_oplaty_za_publikacje(
                    original,
                    # Publikacja bezkosztowa
                    row[4],
                    # Środki finansowe o których mowa w artykule 365
                    row[5],
                    # Środki finansowe na realizację projektu
                    row[6],
                    # Inne srodki finansowe
                    row[7],
                    # Kwota
                    row[8],
                )

                original.save()
