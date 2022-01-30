from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.core.genetyczny import GAD


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dyscyplina", default="nauki medyczne")
        parser.add_argument("--generations", default=1000, type=int)
        parser.add_argument("--saturate", default=300, type=int)
        parser.add_argument("--output-path", default=None, type=str)

    @transaction.atomic
    def handle(self, dyscyplina, generations, output_path, saturate, *args, **options):

        algorytm = GAD(
            nazwa_dyscypliny=dyscyplina,
            max_gen=generations,
            output_path=output_path,
            saturate=saturate,
        )
        algorytm.powitanie()
        algorytm.pracuj()
        algorytm.zrzuc_dane("genetyczny")
        algorytm.pozegnanie()
