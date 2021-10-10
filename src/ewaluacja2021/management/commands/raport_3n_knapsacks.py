# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.core import Plecakowy


class Command(BaseCommand):
    help = "Odbudowuje pola slug"

    @transaction.atomic
    def handle(self, dyscyplina="nauki medyczne", liczba_n=None, *args, **options):

        algorytm = Plecakowy(nazwa_dyscypliny=dyscyplina, liczba_n=liczba_n)
        algorytm.powitanie()
        algorytm.sumuj()
        algorytm.zrzuc_dane("knapsacks")
        algorytm.pozegnanie()
