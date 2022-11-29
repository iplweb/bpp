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


class Command(BaseCommand):
    help = "Import opłat za publikację wg formatu z UML"
    args = "<plik xls 1> <plik xls 2> ..."

    def add_arguments(self, parser: OptionParser):
        parser.add_argument("pliki", type=argparse.FileType("rb"), nargs="+")

    @transaction.atomic
    def handle(self, pliki, *args, **options):

        for plik in pliki:
            xlsx = pandas.read_excel(plik)

            for row in xlsx.iloc:
                pk = normalize_rekord_id(row[0])
                if pk is None:
                    continue

                rekord = Rekord.objects.get(pk=pk)
                original: ModelZOplataZaPublikacje = rekord.original

                normalize_oplaty_za_publikacje(
                    original,
                    # Publikacja bezkosztowa
                    row[2],
                    # Środki finansowe o których mowa w artykule 365
                    row[3],
                    # Środki finansowe na realizację projektu
                    row[4],
                    # Inne srodki finansowe
                    row[5],
                    # Kwota
                    row[1],
                )

                original.save()
