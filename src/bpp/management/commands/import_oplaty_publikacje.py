import argparse
from optparse import OptionParser

import pandas
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import ModelZOplataZaPublikacje, Rekord
from bpp.models.oplaty_log import log_oplaty_change
from import_common.normalization import (
    normalize_oplaty_za_publikacje,
    normalize_rekord_id,
)


class Command(BaseCommand):
    help = 'Import opłat za publikację wg "własnego" formatu z BPP'
    args = "<plik xls 1> <plik xls 2> ..."

    def add_arguments(self, parser: OptionParser):
        parser.add_argument(
            "--dry", action=argparse.BooleanOptionalAction, default=False
        )
        parser.add_argument("pliki", type=argparse.FileType("rb"), nargs="+")

    @transaction.atomic
    def handle(self, dry, pliki, *args, **options):
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
                continue

            for wiersz, row in xlsx.iterrows():
                pk = normalize_rekord_id(row.iloc[1])
                if pk is None:
                    continue

                try:
                    rekord = Rekord.objects.get(pk=pk)
                except Rekord.DoesNotExist:
                    print(f"Brak w bazie rekordu o ID = {pk}")
                    continue
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
                        f"wiersz {wiersz + 2} -- tytuł rekordu inny niz w bazie, nie importuję (plik: "
                        f"{row['Tytuł oryginalny']}, baza {rekord.tytul_oryginalny})"
                    )
                    print()
                    continue

                try:
                    normalize_oplaty_za_publikacje(
                        original,
                        # Publikacja bezkosztowa
                        row.iloc[4],
                        # Środki finansowe o których mowa w artykule 365
                        row.iloc[5],
                        # Środki finansowe na realizację projektu
                        row.iloc[6],
                        # Inne srodki finansowe
                        row.iloc[7],
                        # Kwota
                        row.iloc[8],
                    )
                except ValidationError as e:
                    print(
                        f"wiersz {wiersz + 2} -- problem z walidacją rekordu {rekord.tytul_oryginalny} -- "
                        f"{e}. Zmiany nie zostały wprowadzone do bazy. "
                    )
                    print()
                    continue

                log_oplaty_change(
                    original,
                    changed_by="import_oplaty_publikacje",
                    source_file=plik.name,
                    source_row=wiersz + 2,
                    new_opl_pub_cost_free=original.opl_pub_cost_free,
                    new_opl_pub_research_potential=original.opl_pub_research_potential,
                    new_opl_pub_research_or_development_projects=original.opl_pub_research_or_development_projects,
                    new_opl_pub_other=original.opl_pub_other,
                    new_opl_pub_amount=original.opl_pub_amount,
                )
                original.save()

        if dry:
            transaction.set_rollback(True)
