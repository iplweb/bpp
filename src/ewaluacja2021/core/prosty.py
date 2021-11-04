from random import random

from ..util import shuffle_array
from .mixins import Ewaluacja3NMixin


class Prosty(Ewaluacja3NMixin):
    def __init__(
        self,
        lista_prac,
        nazwa_dyscypliny="nauki medyczne",
        liczba_n=None,
        maks_pkt_aut_calosc=None,
        maks_pkt_aut_monografia=None,
    ):
        self.lista_prac = lista_prac

        Ewaluacja3NMixin.__init__(
            self=self,
            nazwa_dyscypliny=nazwa_dyscypliny,
            liczba_n=liczba_n,
            maks_pkt_aut_calosc=maks_pkt_aut_calosc,
            maks_pkt_aut_monografie=maks_pkt_aut_monografia,
        )

        self.get_data()

    def get_data(self):
        return

    def get_ordered_lista_prac(self):
        return self.lista_prac

    def sumuj(self):
        self.zeruj()

        self.aktualna_lista_prac = self.get_ordered_lista_prac()

        for praca in self.aktualna_lista_prac:
            if not self.czy_moze_przejsc(praca):
                continue
            self.zsumuj_pojedyncza_prace(praca)

    def promuj_obecna_liste(self):
        self.lista_prac = self.aktualna_lista_prac

    def ustaw_liste(self, lista):
        self.lista_prac = lista


class Randomizer:
    # 1) najlepsze miejsce startowe
    # 2) najlepsza długość listy
    # 3) najlepsza ilość iteracji

    def __init__(
        self,
        lista,
        start_elem=0,
        end_elem=3000,
        step=100,
        list_size_min=500,
        list_size_max=2502,
        list_step=100,
        no_shuffles=1,
    ):
        self.lista = lista

        self.start_elem = start_elem
        self.end_elem = end_elem
        self.step = step
        self.list_size_min = list_size_min
        self.list_size_max = list_size_max
        self.list_step = list_step
        self.no_shuffles = no_shuffles

        self.reset()

    def reset(
        self,
        start_elem=None,
        end_elem=None,
        step=None,
        no_shuffles=None,
        list_size_min=None,
        list_size_max=None,
        list_step=None,
    ):
        self.a = self.b = None

        if start_elem is None:
            start_elem = self.start_elem + (200 - random.randint(0, 400))

        if end_elem is None:
            end_elem = self.end_elem

        if step is None:
            step = self.step

        if list_size_min is None:
            list_size_min = self.list_size_min

        if list_size_max is None:
            list_size_max = self.list_size_max

        if list_step is None:
            list_step = self.list_step

        if no_shuffles is None:
            no_shuffles = self.no_shuffles

        self.start_range_obj = range(start_elem, end_elem, step)
        self.start_range = iter(self.start_range_obj)

        self.list_length_range_obj = range(list_size_min, list_size_max, list_step)
        self.list_length_range = iter(self.list_length_range_obj)

        self.no_shuffles_range_obj = range(no_shuffles)
        self.no_shuffles_range = iter(self.no_shuffles_range_obj)

        self.current_start_range = None
        self.current_list_length = None
        self.current_no_shuffles = None

        self.a = next(self.start_range)

    def count(self):
        return (
            len(self.start_range_obj)
            * len(self.list_length_range_obj)
            * len(self.no_shuffles_range_obj)
        )

    def __iter__(self):
        return self

    def __next__(self):

        try:
            self.b = next(self.list_length_range)
        except StopIteration:
            try:
                self.a = next(self.start_range)

                self.list_length_range = iter(self.list_length_range_obj)
                self.b = next(self.list_length_range)
            except StopIteration:
                self.a = iter(self.start_range_obj)

                raise StopIteration

        return shuffle_array(self.lista, self.a, self.b, self.no_shuffles)

    def serialize(self):
        return {
            "current_start_range": self.a,
            "current_list_length": self.b,
            "current_no_shuffles": self.current_no_shuffles,
        }
