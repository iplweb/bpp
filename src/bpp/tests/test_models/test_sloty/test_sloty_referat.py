import pytest

from bpp.models.sloty.core import ISlot
from bpp.models.sloty.exceptions import CannotAdapt
from bpp.models.sloty.wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog3,
)


@pytest.mark.django_db
def test_referat_zle_punkty(referat_z_dyscyplinami):
    referat_z_dyscyplinami.punkty_kbn = 31337
    with pytest.raises(CannotAdapt):
        ISlot(referat_z_dyscyplinami)


@pytest.mark.django_db
def test_referat_15_pkt_wos(referat_z_dyscyplinami, baza_wos):
    referat_z_dyscyplinami.punkty_kbn = 15
    referat_z_dyscyplinami.rok = 2021
    referat_z_dyscyplinami.zewnetrzna_baza_danych.create(baza=baza_wos)
    ISlot(referat_z_dyscyplinami)


@pytest.mark.django_db
def test_referat_200_pkt(referat_z_dyscyplinami, baza_wos):
    referat_z_dyscyplinami.punkty_kbn = 200
    referat_z_dyscyplinami.rok = 2021
    ISlot(referat_z_dyscyplinami)


@pytest.mark.django_db
def test_referat_70_pkt(referat_z_dyscyplinami, baza_wos):
    referat_z_dyscyplinami.punkty_kbn = 70
    referat_z_dyscyplinami.rok = 2021
    ISlot(referat_z_dyscyplinami)


@pytest.mark.django_db
def test_referat_20_pkt_z_wydawca(referat_z_dyscyplinami, wydawca):
    referat_z_dyscyplinami.punkty_kbn = 20
    referat_z_dyscyplinami.rok = 2020
    referat_z_dyscyplinami.wydawca = wydawca
    referat_z_dyscyplinami.save()

    wydawca.poziom_wydawcy_set.create(rok=2020, poziom=1)
    res = ISlot(referat_z_dyscyplinami)
    assert res.__class__ == SlotKalkulator_Wydawnictwo_Ciagle_Prog2


@pytest.mark.django_db
def test_referat_20_pkt_bez_wydawcy(referat_z_dyscyplinami):
    referat_z_dyscyplinami.punkty_kbn = 20
    referat_z_dyscyplinami.rok = 2020
    res = ISlot(referat_z_dyscyplinami)
    assert res.__class__ == SlotKalkulator_Wydawnictwo_Ciagle_Prog3


@pytest.mark.django_db
def test_referat_5_pkt_bez_wydawcy(referat_z_dyscyplinami):
    rok = 2021
    referat_z_dyscyplinami.punkty_kbn = 5
    referat_z_dyscyplinami.rok = rok
    res = ISlot(referat_z_dyscyplinami)
    assert res.__class__ == SlotKalkulator_Wydawnictwo_Ciagle_Prog3
