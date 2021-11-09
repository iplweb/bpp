from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.core.genetyczny import GAD


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dyscyplina", default="nauki medyczne")
        parser.add_argument("--generations", default=1000, type=int)
        parser.add_argument("--ile_najlepszych", default=40, type=int)
        parser.add_argument("--ile-losowych", default=50, type=int)
        parser.add_argument("--ile-zupelnie-losowych", default=30, type=int)

    @transaction.atomic
    def handle(
        self,
        dyscyplina,
        generations,
        ile_najlepszych,
        ile_losowych,
        ile_zupelnie_losowych,
        liczba_n=None,
        *args,
        **options
    ):

        algorytm = GAD(
            nazwa_dyscypliny=dyscyplina,
            max_gen=generations,
            ile_najlepszych=ile_najlepszych,
            ile_losowych=ile_losowych,
            ile_zupelnie_losowych=ile_zupelnie_losowych,
        )
        algorytm.powitanie()
        algorytm.pracuj()
        algorytm.pozegnanie()
