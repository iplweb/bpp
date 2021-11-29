from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.core.plecakowy import Plecakowy


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dyscyplina", default="nauki medyczne")
        parser.add_argument("--bez-limitu-uczelni", type=bool, default=False)
        parser.add_argument("--output-path", default=None, type=str)

    @transaction.atomic
    def handle(self, dyscyplina, output_path, bez_limitu_uczelni, *args, **options):

        algorytm = Plecakowy(
            nazwa_dyscypliny=dyscyplina,
            bez_limitu_uczelni=bez_limitu_uczelni,
            output_path=output_path,
        )
        algorytm.powitanie()
        algorytm.sumuj()
        algorytm.zrzuc_dane("plecakowy")
        algorytm.pozegnanie()
