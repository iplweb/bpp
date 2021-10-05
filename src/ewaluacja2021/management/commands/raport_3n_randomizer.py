# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from ewaluacja2021.core import Prosty, ZmieniajacyKolejnosc, get_lista_prac_as_tuples


def sumuj_chunk(listy_prac):

    maks_suma_pkd = maks_output = maks_sumy_slotow = None

    for lista_prac in listy_prac:
        output, suma_pkd, sumy_slotow = Prosty(lista_prac).sumuj()

        if maks_suma_pkd is None or suma_pkd > maks_suma_pkd:
            maks_output = output
            maks_suma_pkd = suma_pkd
            maks_sumy_slotow = sumy_slotow

    return maks_output, maks_suma_pkd, maks_sumy_slotow


class Command(BaseCommand):
    help = "Odbudowuje pola slug"

    @transaction.atomic
    def handle(self, dyscyplina="nauki medyczne", liczba_n=None, *args, **options):

        lista_prac = get_lista_prac_as_tuples(dyscyplina)
        algorytm = ZmieniajacyKolejnosc(
            lista_prac, nazwa_dyscypliny=dyscyplina, liczba_n=liczba_n
        )
        algorytm.powitanie()

        maks_suma_pkd = None

        for a in range(500):
            algorytm.sumuj()

            if maks_suma_pkd is None or algorytm.suma_pkd > maks_suma_pkd:
                # maks_output = algorytm.id_rekordow
                maks_suma_pkd = algorytm.suma_pkd
                # maks_sumy_slotow = algorytm.sumy_slotow

                algorytm.pozegnanie()
