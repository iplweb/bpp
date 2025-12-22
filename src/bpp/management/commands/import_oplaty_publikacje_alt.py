import argparse
from optparse import OptionParser

import pandas
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import ModelZOplataZaPublikacje, Rekord
from bpp.models.oplaty_log import log_oplaty_change
from bpp.util import pbar
from import_common.normalization import (
    normalize_oplaty_za_publikacje,
    normalize_rekord_id,
)


class Command(BaseCommand):
    help = "Import opłat za publikację wg formatu z UML"
    args = "<plik xls 1> <plik xls 2> ..."

    def add_arguments(self, parser: OptionParser):
        parser.add_argument("pliki", type=argparse.FileType("rb"), nargs="+")

    @transaction.atomic
    def handle(self, pliki, *args, **options):
        for plik in pliki:
            xlsx = pandas.read_excel(plik)
            for wiersz, row in enumerate(pbar(xlsx.iloc, count=xlsx.count().iloc[0])):
                pk = normalize_rekord_id(row.iloc[0])
                if pk is None:
                    continue

                rekord = Rekord.objects.get(pk=pk)
                original: ModelZOplataZaPublikacje = rekord.original

                try:
                    normalize_oplaty_za_publikacje(
                        original,
                        # Publikacja bezkosztowa
                        row.iloc[2],
                        # Środki finansowe o których mowa w artykule 365
                        row.iloc[3],
                        # Środki finansowe na realizację projektu
                        row.iloc[4],
                        # Inne srodki finansowe
                        row.iloc[5],
                        # Kwota
                        row.iloc[1],
                    )
                except ValidationError as e:
                    print(
                        f"Problem z walidacją plik {plik} wiersz {wiersz + 2} rekordu "
                        f"{rekord.tytul_oryginalny} -- {e}. Zmiany nie zostały wprowadzone do bazy. "
                    )
                    continue

                log_oplaty_change(
                    original,
                    changed_by="import_oplaty_publikacje_alt",
                    source_file=plik.name,
                    source_row=wiersz + 2,
                    new_opl_pub_cost_free=original.opl_pub_cost_free,
                    new_opl_pub_research_potential=original.opl_pub_research_potential,
                    new_opl_pub_research_or_development_projects=original.opl_pub_research_or_development_projects,
                    new_opl_pub_other=original.opl_pub_other,
                    new_opl_pub_amount=original.opl_pub_amount,
                )
                original.save()
