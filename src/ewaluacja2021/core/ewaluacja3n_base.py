import logging
import os
from decimal import Decimal
from operator import attrgetter

import simplejson

from ..models import LiczbaNDlaUczelni
from .sumator_base import SumatorBase
from .util import (
    encode_datetime,
    get_lista_autorow_na_rekord,
    get_lista_prac,
    lista_prac_na_tuples,
    maks_pkt_aut_calosc_get_from_db,
    maks_pkt_aut_monografie_get_from_db,
)

logger = logging.getLogger(__name__)


class Ewaluacja3NBase(SumatorBase):
    def __init__(self, nazwa_dyscypliny="nauki medyczne", output_path=None):
        """
        maks_pkt_aut_calosc
            maksymalna ilość punktów dla poszczególnych autorów, słownik autor->maks pkt

        maks_pkt_aut_monografie
            maksymalna ilość punktów dla autorów za monografie, słownik autor->maks pkt

        """

        self.nazwa_dyscypliny = nazwa_dyscypliny
        self.output_path = output_path

        maks_pkt_aut_calosc = maks_pkt_aut_calosc_get_from_db(self.nazwa_dyscypliny)

        maks_pkt_aut_monografie = maks_pkt_aut_monografie_get_from_db(
            self.nazwa_dyscypliny
        )

        self.liczba_n = LiczbaNDlaUczelni.objects.get(
            dyscyplina_naukowa__nazwa=self.nazwa_dyscypliny
        ).liczba_n

        SumatorBase.__init__(
            self=self,
            liczba_2_2_n=Decimal("2.2") * self.liczba_n,
            liczba_0_8_n=Decimal("0.8") * self.liczba_n,
            maks_pkt_aut_calosc=maks_pkt_aut_calosc,
            maks_pkt_aut_monografie=maks_pkt_aut_monografie,
        )

    def get_data(self):
        logger.info("get_data start")
        self.autorzy_na_rekord = get_lista_autorow_na_rekord(self.nazwa_dyscypliny)

        self.id_wszystkich_autorow = set()
        for elem in self.autorzy_na_rekord.values():
            for x in elem:
                self.id_wszystkich_autorow.add(x)

        self.lista_prac_db = get_lista_prac(self.nazwa_dyscypliny)
        self.lista_prac_tuples = lista_prac_na_tuples(
            self.lista_prac_db, self.autorzy_na_rekord
        )
        logger.info("get_data finished")

    def powitanie(self):
        print(
            f"Szukam dla: {self.nazwa_dyscypliny}, liczba N: {self.liczba_n}, 2.2*N: {self.liczba_2_2_n}, "
            f"0.8*N: {self.liczba_0_8_n}"
        )

    def pozegnanie(self):
        print(
            f"Obecna maks pkd: {self.suma_pkd}, suma slotow: {self.sumy_slotow}, ilosc prac: {len(self.id_rekordow)}"
        )

    def zrzuc_dane(self, nazwa):
        output = {
            "ostatnia_zmiana": getattr(
                max(self.lista_prac, key=attrgetter("ostatnio_zmieniony")),
                "ostatnio_zmieniony",
                "brak rekordów",
            ),
            "dyscyplina": self.nazwa_dyscypliny,
            "liczba_n": self.liczba_n,
            "liczba_0_8_n": self.liczba_0_8_n,
            "liczba_2_2_n": self.liczba_2_2_n,
            "sumy_slotow": self.sumy_slotow,
            "maks_pkt_aut_calosc": self.maks_pkt_aut_calosc,
            "maks_pkt_aut_monografie": self.maks_pkt_aut_monografie,
            "wejscie": [x for x in self.lista_prac],
            "optimum": [x for x in self.id_rekordow],
        }

        nazwa = nazwa + "_" + self.nazwa_dyscypliny.replace(" ", "_") + ".json"

        if self.output_path is not None:
            nazwa = os.path.abspath(os.path.join(self.output_path, nazwa))

        with open(nazwa, "w") as f:
            simplejson.dump(
                output,
                f,
                indent=4,
                use_decimal=True,
                namedtuple_as_object=True,
                tuple_as_array=True,
                default=encode_datetime,
            )

        print(f"Dane zrzucone do {nazwa}")
