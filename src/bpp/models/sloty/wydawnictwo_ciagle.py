from decimal import Decimal
from math import sqrt

from .common import SlotMixin


class SlotKalkulator_Wydawnictwo_Ciagle_Prog1(SlotMixin):
    """
    Artykuł z czasopisma z listy ministerialnej.
    Dla roku 2017, 2018: punkty KBN >= 30
    """

    def punkty_pkd(self, dyscyplina):
        if self.ma_dyscypline(dyscyplina):
            return self.original.punkty_kbn

    def slot_dla_autora_z_dyscypliny(self, dyscyplina):
        azd = self.autorzy_z_dyscypliny(dyscyplina).count()
        if azd == 0:
            return
        return Decimal("1") / azd

    def slot_dla_dyscypliny(self, dyscyplina):
        if self.ma_dyscypline(dyscyplina):
            return Decimal("1")


class SlotKalkulator_Wydawnictwo_Ciagle_Prog2(SlotMixin):
    """
    Artykuł z czasopisma z listy ministerialnej.

    Dla roku 2017-2018: punkty KBN 20 lub 25
    """

    def pierwiastek_k_przez_m(self, dyscyplina):
        return sqrt(self.autorzy_z_dyscypliny(dyscyplina).count() / self.wszyscy())

    def punkty_pkd(self, dyscyplina):
        if self.ma_dyscypline(dyscyplina):
            return self.original.punkty_kbn * self.pierwiastek_k_przez_m(dyscyplina)

    def slot_dla_autora_z_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return
        
        azd = self.autorzy_z_dyscypliny(dyscyplina).count()
        if azd > 0:
            return self.pierwiastek_k_przez_m(dyscyplina) * 1 / azd

    def slot_dla_dyscypliny(self, dyscyplina):
        if not self.ma_dyscypline(dyscyplina):
            return

        return self.pierwiastek_k_przez_m(dyscyplina)
