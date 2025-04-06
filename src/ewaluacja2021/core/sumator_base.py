import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SumatorBase:
    def __init__(
        self,
        liczba_3n,
        procent_monografii,
        maks_pkt_aut_calosc,
        maks_pkt_aut_monografie,
    ):
        self.liczba_3n = liczba_3n
        self.liczba_3n_monografie = liczba_3n * procent_monografii

        # mapa autor -> ile slotów
        self.maks_pkt_aut_calosc = maks_pkt_aut_calosc

        # mapa autor -> ile slotów za monografie
        self.maks_pkt_aut_monografie = maks_pkt_aut_monografie

        self.zeruj()

    def czy_moze_przejsc_warunek_uczelnia(self, praca):
        if praca.monografia:
            if praca.poziom_wydawcy != 2:
                # maksymalnie 5% monografii lub 20% w przypadku HST
                if self.suma_slotow_monografie + praca.slot > self.liczba_3n_monografie:
                    return False

        if self.suma_slotow + praca.slot > self.liczba_3n:
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

        self.suma_slotow += praca.slot
        self.suma_prac_autorow_wszystko[praca.autor_id] += praca.slot
        if praca.monografia:
            self.suma_prac_autorow_monografie[praca.autor_id] += praca.slot

    def zeruj(self):
        self.id_rekordow = set()

        self.suma_pkd = 0
        self.suma_slotow = 0
        self.suma_slotow_monografie = 0
        self.indeksy_solucji = set()

        self.suma_prac_autorow_wszystko = defaultdict(int)
        self.suma_prac_autorow_monografie = defaultdict(int)
