from decimal import Decimal

from .common import SlotMixin


class SlotKalkulator_Wydawnictwo_Ciagle_Prog1(SlotMixin):
    """
    Artykuł z czasopisma z listy ministerialnej.
    Dla roku 2017, 2018: punkty MNiSW/MEiN >= 30
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


class SlotKalkulator_Wydawnictwo_Ciagle_Prog2(SlotMixin):
    """
    Artykuł z czasopisma z listy ministerialnej.

    Dla roku 2017-2018: punkty MNiSW/MEiN 20 lub 25
    """

    def punkty_pkd(self, dyscyplina):
        if self.ma_dyscypline(dyscyplina):
            pierwiastek = self.pierwiastek_k_przez_m(dyscyplina)
            if pierwiastek is None:
                return None

            if self.liczba_k(dyscyplina) == 0:
                return 0

            return self.original.punkty_kbn * max(pierwiastek, Decimal("0.1"))

    def slot_dla_autora_z_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return

        azd = len(self.autorzy_z_dyscypliny(dyscyplina))
        if azd > 0:
            return self.pierwiastek_k_przez_m(dyscyplina) * 1 / azd

    def slot_dla_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return

        return self.pierwiastek_k_przez_m(dyscyplina)


class SlotKalkulator_Wydawnictwo_Ciagle_Prog3(SlotMixin):
    """
    Artykuł z czasopisma z listy ministerialnej.

    Dla roku 2017-2018: punkty MNiSW/MEiN poniżej 20 lub 5
    """

    def punkty_pkd(self, dyscyplina):
        if self.ma_dyscypline(dyscyplina):
            k_przez_m = self.k_przez_m(dyscyplina)
            if k_przez_m is None:
                return
            if self.liczba_k(dyscyplina) == 0:
                return 0
            return self.original.punkty_kbn * max(k_przez_m, Decimal("0.1"))

    def slot_dla_autora_z_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return
        return self.jeden_przez_wszyscy()

    def slot_dla_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return
        return self.jeden_przez_wszyscy() * len(self.autorzy_z_dyscypliny(dyscyplina))
