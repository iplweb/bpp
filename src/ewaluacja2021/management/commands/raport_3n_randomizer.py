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
    @transaction.atomic
    def handle(self, dyscyplina="nauki medyczne", liczba_n=None, *args, **options):

        lista_prac = get_lista_prac_as_tuples(dyscyplina)
        algorytm = ZmieniajacyKolejnosc(
            lista_prac, nazwa_dyscypliny=dyscyplina, liczba_n=liczba_n
        )
        algorytm.powitanie()

        maks_lista_prac = baza = maks_suma_pkd = None

        nr_cyklu = 0
        while True:
            count = algorytm.randomizer.count()
            for a in range(count):  # , label=f"Nr cyklu: {nr_cyklu}"):
                algorytm.sumuj()

                if maks_suma_pkd is None or algorytm.suma_pkd > maks_suma_pkd:

                    # maks_output = algorytm.id_rekordow
                    maks_suma_pkd = algorytm.suma_pkd
                    maks_lista_prac = algorytm.aktualna_lista_prac
                    if baza is None:
                        baza = maks_suma_pkd
                    # maks_sumy_slotow = algorytm.sumy_slotow

                    print(maks_suma_pkd - baza, algorytm.randomizer.serialize())

                    # algorytm.pozegnanie()

                    # algorytm.promuj_obecna_liste()
                    baza = maks_suma_pkd

                    print("Ustawiam jako bazowa liste z %i pkd" % maks_suma_pkd)
                    algorytm.ustaw_liste(maks_lista_prac)
                    algorytm.zrzuc_dane("randomizer")
                    maks_lista_prac = None

            algorytm.randomizer.reset()

            nr_cyklu += 1
            # algorytm.randomizer.reset()
            #
            # if nr_cyklu < 10:
            #
            # else:
            #     while True:
            #         try:
            #             maxlen = len(algorytm.lista_prac)
            #
            #             list_len = 3000
            #
            #             algorytm.randomizer.reset(
            #                 start_elem=0,
            #                 end_elem=maxlen - list_len,
            #                 list_size_min=1000,
            #                 list_size_max=list_len,
            #                 list_step=50,
            #             )
            #             break
            #         except ValueError:
            #             pass
            #
            # continue
