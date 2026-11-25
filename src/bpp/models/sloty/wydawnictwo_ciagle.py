from decimal import Decimal

from .common import SlotMixin


class SlotKalkulator_Wydawnictwo_Ciagle_Prog1(SlotMixin):
    """
    Artykuł z czasopisma z listy ministerialnej.
    Dla roku 2017, 2018: punkty MNiSW >= 30
    """

    def punkty_pkd(self, dyscyplina):
        if self.ma_dyscypline(dyscyplina):
            return self.original.punkty_kbn

    def slot_dla_autora_z_dyscypliny(self, dyscyplina):
        azd = len(self.autorzy_z_dyscypliny(dyscyplina))
        if azd == 0:
            return
        return Decimal("1") / azd

    def slot_dla_dyscypliny(self, dyscyplina):
        if self.ma_dyscypline(dyscyplina):
            return Decimal("1")


MINIMUM_UDZIALU = Decimal("0.1")


class SlotKalkulator_Wspolczynnik_K_M(SlotMixin):
    """Wspólna część progów 2 i 3: punkty = PK × współczynnik, gdzie
    współczynnik to √(k/m) (próg 2) albo k/m (próg 3), zaokrąglony do 4 miejsc
    (§ 13 ust. 6), ale nie mniej niż 0,1 („nie mniej niż 10 % tej wartości”,
    § 13 ust. 1, 3 i 5).

    Sloty wynikają z tej samej (podniesionej do minimum) wartości:
    udział jednostkowy U = P/Pc × 1/k (§ 16 ust. 2), czyli slot dyscypliny
    = P/Pc = współczynnik, a slot autora = współczynnik / k. Np. 70 pkt,
    k = 1, m = 150: √(1/150) = 0,0816 < 0,1, więc P = 7,0000 i slot 0,1000.
    """

    def wartosc_k_m(self, dyscyplina):
        raise NotImplementedError

    def wspolczynnik(self, dyscyplina):
        """P/Pc dla dyscypliny; None gdy rekord nie ma autorów (m = 0),
        0 gdy nie ma autorów z dyscypliny (k = 0)."""
        wartosc = self.wartosc_k_m(dyscyplina)
        if wartosc is None:
            return None
        if self.liczba_k(dyscyplina) == 0:
            return wartosc  # 0,0000 — brak autorów z afiliacją, bez minimum
        return max(wartosc, MINIMUM_UDZIALU)

    def punkty_pkd(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return
        wspolczynnik = self.wspolczynnik(dyscyplina)
        if wspolczynnik is None:
            return
        if self.liczba_k(dyscyplina) == 0:
            return 0
        return self.original.punkty_kbn * wspolczynnik

    def slot_dla_autora_z_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return
        k = self.liczba_k(dyscyplina)
        if k == 0:
            return
        wspolczynnik = self.wspolczynnik(dyscyplina)
        if wspolczynnik is None:
            return
        return wspolczynnik / k

    def slot_dla_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return
        return self.wspolczynnik(dyscyplina)


class SlotKalkulator_Wydawnictwo_Ciagle_Prog2(SlotKalkulator_Wspolczynnik_K_M):
    """
    Artykuł z czasopisma z listy ministerialnej.

    Dla roku 2017-2018: punkty MNiSW 20 lub 25
    """

    def wartosc_k_m(self, dyscyplina):
        return self.pierwiastek_k_przez_m(dyscyplina)


class SlotKalkulator_Wydawnictwo_Ciagle_Prog3(SlotKalkulator_Wspolczynnik_K_M):
    """
    Artykuł z czasopisma z listy ministerialnej.

    Dla roku 2017-2018: punkty MNiSW poniżej 20 lub 5
    """

    def wartosc_k_m(self, dyscyplina):
        return self.k_przez_m(dyscyplina)
