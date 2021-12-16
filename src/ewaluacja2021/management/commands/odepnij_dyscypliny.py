from argparse import FileType

from denorm import denorms
from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.reports import load_data, rekordy


class Command(BaseCommand):
    """Odpina dyscypliny, bazujac na JSON"""

    def add_arguments(self, parser):
        parser.add_argument("wejscie", type=FileType("r"))

    def handle(self, wejscie, *args, **options):

        dane = load_data(wejscie)

        rekordy_danych = rekordy(dane)
        a = 0

        with transaction.atomic():
            for rekord in rekordy_danych.exclude(do_ewaluacji=True).exclude(slot=1):
                original = rekord.rekord.original
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
                    a += 1

        print(f"Odpieto {a} dyscyplin; przeliczam...")
        denorms.flush()
