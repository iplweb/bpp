import pytest

from raport_slotow.core import (
    autorzy_z_dyscyplinami,
    autorzy_z_punktami,
    autorzy_zerowi,
)


def test_autorzy_z_dyscyplinami_parametr(autor_z_dyscyplina, rok):
    assert autorzy_z_dyscyplinami(od_roku=rok, do_roku=rok).count() == 1


def test_autorzy_z_dyscyplinami_bez_parametru(autor_z_dyscyplina, rok):
    assert autorzy_z_dyscyplinami().count() == 1


def test_autorzy_z_dyscyplinami_poza_zakr(autor_z_dyscyplina, rok):
    assert autorzy_z_dyscyplinami(od_roku=rok + 10).count() == 0
    assert autorzy_z_dyscyplinami(do_roku=rok + 10).count() == 1


def test_autorzy_z_punktami_autor_nie_ma(autor_jan_nowak):
    assert autorzy_z_punktami().count() == 0


def test_autorzy_z_punktami_autor_nadal_nie_ma(autor_z_dyscyplina):
    assert autorzy_z_punktami().count() == 0


@pytest.mark.django_db
def test_autorzy_z_punktami_autor_ma(praca_z_dyscyplina):
    assert autorzy_z_punktami().count() == 1


@pytest.mark.django_db
def test_autorzy_zerowi(rekord_slotu, autor_z_dyscyplina):
    assert autorzy_zerowi().count() == 1


@pytest.mark.django_db
def test_autorzy_zerowi_rok_powyzej(rekord_slotu, autor_jan_nowak, rok):
    assert autorzy_zerowi(od_roku=rok + 20).count() == 0
