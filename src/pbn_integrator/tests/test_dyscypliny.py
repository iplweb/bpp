"""Unit testy helpera przypisz_dyscypline_pbn."""

from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa
from pbn_integrator.utils.dyscypliny import (
    WynikPrzypisaniaDyscypliny,
    przypisz_dyscypline_pbn,
)

ROK = 2022


@pytest.fixture
def autor(db):
    return baker.make(Autor)


@pytest.fixture
def dyscyplina_X(db):
    return baker.make(Dyscyplina_Naukowa, nazwa="nauki medyczne", kod="3.2")


@pytest.fixture
def dyscyplina_Y(db):
    return baker.make(Dyscyplina_Naukowa, nazwa="psychologia", kod="5.11")


@pytest.fixture
def dyscyplina_Z(db):
    return baker.make(Dyscyplina_Naukowa, nazwa="nauki prawne", kod="5.7")


@pytest.mark.django_db
def test_brak_wiersza_tworzy_z_procentem_100(autor, dyscyplina_X):
    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_X)

    assert wynik == WynikPrzypisaniaDyscypliny.UTWORZONO
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina_X
    assert ad.procent_dyscypliny == Decimal("100.00")
    assert ad.subdyscyplina_naukowa is None


@pytest.mark.django_db
def test_dyscyplina_juz_glowna_brak_zmian(autor, dyscyplina_X):
    baker.make(
        Autor_Dyscyplina, autor=autor, rok=ROK, dyscyplina_naukowa=dyscyplina_X
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_X)

    assert wynik == WynikPrzypisaniaDyscypliny.BRAK_ZMIAN
    assert Autor_Dyscyplina.objects.filter(autor=autor, rok=ROK).count() == 1


@pytest.mark.django_db
def test_dyscyplina_juz_jako_sub_brak_zmian(autor, dyscyplina_X, dyscyplina_Y):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        subdyscyplina_naukowa=dyscyplina_Y,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Y)

    assert wynik == WynikPrzypisaniaDyscypliny.BRAK_ZMIAN


@pytest.mark.django_db
def test_pusty_sub_auto_procenty_50_50(autor, dyscyplina_X, dyscyplina_Y):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        procent_dyscypliny=Decimal("100.00"),
        subdyscyplina_naukowa=None,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Y)

    assert wynik == WynikPrzypisaniaDyscypliny.DODANO_SUB
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.subdyscyplina_naukowa == dyscyplina_Y
    assert ad.procent_dyscypliny == Decimal("50.00")
    assert ad.procent_subdyscypliny == Decimal("50.00")


@pytest.mark.django_db
def test_pusty_sub_z_recznym_podzialem_nie_rusza_procentow(
    autor, dyscyplina_X, dyscyplina_Y
):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        procent_dyscypliny=Decimal("70.00"),
        subdyscyplina_naukowa=None,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Y)

    assert wynik == WynikPrzypisaniaDyscypliny.DODANO_SUB
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.subdyscyplina_naukowa == dyscyplina_Y
    assert ad.procent_dyscypliny == Decimal("70.00")  # nietknięte
    assert ad.procent_subdyscypliny is None  # do weryfikacji


@pytest.mark.django_db
def test_oba_sloty_zajete_konflikt(autor, dyscyplina_X, dyscyplina_Y, dyscyplina_Z):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        subdyscyplina_naukowa=dyscyplina_Y,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Z)

    assert wynik == WynikPrzypisaniaDyscypliny.KONFLIKT_BRAK_MIEJSCA
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina_X  # bez zmian
    assert ad.subdyscyplina_naukowa == dyscyplina_Y  # bez zmian
