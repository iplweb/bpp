import pytest

from bpp.models.sloty.core import ISlot
from bpp.models.sloty.wydawnictwo_zwarte import (
    SlotKalkulator_Wydawnictwo_Zwarte_Prog1,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog3,
)


@pytest.mark.django_db
def test_ISlot_tlumaczenie_tier3(zwarte_z_dyscyplinami):
    rok = 2021
    zwarte_z_dyscyplinami.rok = rok
    i = ISlot(zwarte_z_dyscyplinami)
    zwarte_z_dyscyplinami.punkty_kbn = 2.5
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)


@pytest.mark.django_db
def test_ISlot_tlumaczenie_tier2(zwarte_z_dyscyplinami, wydawca):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    zwarte_z_dyscyplinami.punkty_kbn = 40
    zwarte_z_dyscyplinami.rok = rok
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)


@pytest.mark.django_db
def test_ISlot_tlumaczenie_tier1(zwarte_z_dyscyplinami, wydawca):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    zwarte_z_dyscyplinami.punkty_kbn = 100
    zwarte_z_dyscyplinami.rok = rok
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog1)
