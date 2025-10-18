from argparse import FileType

from denorm import denorms
from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.reports import load_data, rekordy


class Command(BaseCommand):
    """Odpina dyscypliny, bazujac na JSON"""

    def add_arguments(self, parser):
        parser.add_argument("wejscie", type=FileType("r"))
        parser.add_argument("--ostatecznie", action="store_true", default=False)

    def handle(self, wejscie, ostatecznie, *args, **options):
        dane = load_data(wejscie)

        rekordy_danych = rekordy(dane)

        query = rekordy_danych.exclude(do_ewaluacji=True).exclude(slot=1)
        if ostatecznie:
            # Odpinanie ostateczne -- odpinaj wszystkie dyscypliny na koniec raportu
            query = rekordy_danych.exclude(do_ewaluacji=True)

        with transaction.atomic():
            for rekord in query:
                original = rekord.rekord.original
                if ostatecznie:
                    original.autorzy_set.filter(
                        autor=rekord.autor, dyscyplina_naukowa=rekord.dyscyplina
                    ).update(przypieta=False)
                    continue

                # Odpinaj tylko w pracach, gdzie jest więcej jak jeden autor, ktoremu mozna odpiac:
                if (
                    original.autorzy_set.exclude(dyscyplina_naukowa_id=None)
                    .filter(przypieta=True)
                    .count()
                    > 1
                ):
                    original.autorzy_set.filter(
                        autor=rekord.autor, dyscyplina_naukowa=rekord.dyscyplina
                    ).update(przypieta=False)

        denorms.flush()
