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


class Command(BaseCommand):
    help = 'Import opłat za publikację wg "własnego" formatu z BPP'
    args = "<plik xls 1> <plik xls 2> ..."

    def add_arguments(self, parser: OptionParser):
        parser.add_argument("pliki", type=argparse.FileType("rb"), nargs="+")

    @transaction.atomic
    def handle(self, pliki, *args, **options):

        for plik in pliki:
            print()
            print()
            print()
            print(plik.name)
            print("=" * 80)
            print()

            try:
                xlsx = pandas.read_excel(plik)
            except ValueError:
                print(f"Nie umiem otworzyc pliku {plik.name}")

            for wiersz, row in enumerate(xlsx.iloc):
                pk = normalize_rekord_id(row[1])
                if pk is None:
                    continue

                rekord = Rekord.objects.get(pk=pk)
                original: ModelZOplataZaPublikacje = rekord.original

                try:
                    row["Tytuł oryginalny"]
                except KeyError:
                    print(
                        "Plik nie ma kolumny 'Tytuł oryginalny', nie importuję pliku w ogóle"
                    )
                    continue

                if rekord.tytul_oryginalny != row["Tytuł oryginalny"]:
                    print(
                        f"wiersz {wiersz} -- tytuł rekordu inny niz w bazie, nie importuję (plik: "
                        f"{row['Tytuł oryginalny']}, baza {rekord.tytul_oryginalny})"
                    )
                    print()
                    continue

                try:
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
                except ValidationError as e:
                    print(
                        f"wiersz {wiersz} -- problem z walidacją rekordu {rekord.tytul_oryginalny} -- "
                        f"{e}. Zmiany nie zostały wprowadzone do bazy. "
                    )
                    print()
                    continue

                original.save()
