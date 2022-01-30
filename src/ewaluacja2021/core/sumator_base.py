import logging
from collections import defaultdict

from ewaluacja2021.const import LATA_2017_2018, LATA_2019_2021

logger = logging.getLogger(__name__)


class SumatorBase:
    def __init__(
        self, liczba_2_2_n, liczba_0_8_n, maks_pkt_aut_calosc, maks_pkt_aut_monografie
    ):
        self.liczba_2_2_n = liczba_2_2_n
        self.liczba_0_8_n = liczba_0_8_n
        self.maks_pkt_aut_calosc = maks_pkt_aut_calosc
        self.maks_pkt_aut_monografie = maks_pkt_aut_monografie
        self.liczba_2_2_n_minus_2 = self.liczba_2_2_n - 2
        self.liczba_0_8_n_minus_2 = self.liczba_0_8_n - 2

        self.zeruj()

    def czy_moze_przejsc_warunek_uczelnia(self, praca):
        if (
            self.sumy_slotow[LATA_2019_2021] < self.liczba_2_2_n_minus_2
            and self.sumy_slotow[LATA_2017_2018] < self.liczba_0_8_n_minus_2
        ):
            return True

        # Czy uczelnia nie ma już dość takich publikacji?
        if praca.rok >= 2019 or praca.monografia:
            if self.sumy_slotow[LATA_2019_2021] + praca.slot > self.liczba_2_2_n:
                return False
        else:
            if self.sumy_slotow[LATA_2017_2018] + praca.slot > self.liczba_0_8_n:
                return False

        # Uczelnia nie ma dość takich publikacji. Idziemy dalej.
        return True

    def czy_moze_przejsc_warunek_autor(self, praca):
        # Czy autor nie ma dość takich publikacji?
        if self.suma_prac_autorow_wszystko[
            praca.autor_id
        ] + praca.slot > self.maks_pkt_aut_calosc.get(praca.autor_id):
            return False

        # Jeżeli to jest monografia - czy autor nie ma dość już takich punktów za monografię?
        if praca.monografia:
            if self.suma_prac_autorow_monografie[
                praca.autor_id
            ] + praca.slot > self.maks_pkt_aut_monografie.get(praca.autor_id):
                return False

        return True

    def czy_moze_przejsc(self, praca):
        if (
            praca.id not in self.id_rekordow
            and self.czy_moze_przejsc_warunek_uczelnia(praca)
            and self.czy_moze_przejsc_warunek_autor(praca)
        ):
            return True

    def zsumuj_pojedyncza_prace(self, praca, indeks_solucji=None):
        self.suma_pkd += praca.pkdaut

        # Tu dodajemy Cache_Punktacja_Autora.id, nie zaś rekord_id
        self.id_rekordow.add(praca.id)
        if indeks_solucji is not None:
            self.indeksy_solucji.add(indeks_solucji)

        if praca.rok >= 2019 or praca.monografia:
            self.sumy_slotow[LATA_2019_2021] += praca.slot
        else:
            self.sumy_slotow[LATA_2017_2018] += praca.slot

        self.suma_prac_autorow_wszystko[praca.autor_id] += praca.slot
        if praca.monografia:
            self.suma_prac_autorow_monografie[praca.autor_id] += praca.slot

    def zeruj(self):
        self.id_rekordow = set()

        self.suma_pkd = 0
        self.sumy_slotow = [0, 0]
        self.indeksy_solucji = set()

        self.suma_prac_autorow_wszystko = defaultdict(int)
        self.suma_prac_autorow_monografie = defaultdict(int)
