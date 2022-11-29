import argparse
from optparse import OptionParser

import pandas
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand
from django.db import transaction

from import_common.normalization import (
    normalize_oplaty_za_publikacje,
    normalize_rekord_id,
)

from bpp.models import ModelZOplataZaPublikacje, Rekord
from bpp.util import pbar


class Command(BaseCommand):
    help = "Import opłat za publikację wg formatu z UML"
    args = "<plik xls 1> <plik xls 2> ..."

    def add_arguments(self, parser: OptionParser):
        parser.add_argument("pliki", type=argparse.FileType("rb"), nargs="+")

    @transaction.atomic
    def handle(self, pliki, *args, **options):

        for plik in pliki:
            xlsx = pandas.read_excel(plik)
            for wiersz, row in enumerate(pbar(xlsx.iloc, count=xlsx.count()[0])):
                pk = normalize_rekord_id(row[0])
                if pk is None:
                    continue

                rekord = Rekord.objects.get(pk=pk)
                original: ModelZOplataZaPublikacje = rekord.original

                try:
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
                except ValidationError as e:
                    print(
                        f"Problem z walidacją plik {plik} wiersz {wiersz} rekordu "
                        f"{rekord.tytul_oryginalny} -- {e}. Zmiany nie zostały wprowadzone do bazy. "
                    )
                    continue

                original.save()
