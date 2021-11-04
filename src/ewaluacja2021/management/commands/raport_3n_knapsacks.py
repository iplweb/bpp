from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.core.plecakowy import Plecakowy


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dyscyplina", default="nauki medyczne")

    @transaction.atomic
    def handle(self, dyscyplina, liczba_n=None, *args, **options):

        algorytm = Plecakowy(nazwa_dyscypliny=dyscyplina, liczba_n=liczba_n)
        algorytm.powitanie()
        algorytm.sumuj()
        algorytm.zrzuc_dane("knapsacks")
        algorytm.pozegnanie()
