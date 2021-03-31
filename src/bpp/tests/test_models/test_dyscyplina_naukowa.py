import pytest
from django.core.exceptions import ValidationError

from bpp.models import (
    Dyscyplina_Naukowa,
    const,
    mnoznik_dla_monografii,
    waliduj_format_kodu_numer,
)


def test_Dyscyplina_Naukowa_kod_dziedziny():
    assert Dyscyplina_Naukowa(kod="05.32").kod_dziedziny() == 5


def test_Dyscyplina_Naukowa_dziedzina():
    assert (
        Dyscyplina_Naukowa(kod="03.32").dziedzina()
        == const.DZIEDZINY[const.DZIEDZINA.NAUKI_MEDYCZNE]
    )


@pytest.mark.parametrize(
    "kod,tryb,punktacja,wynik",
    [
        (
            const.DZIEDZINA.NAUKI_TEOLOGICZNE,
            const.TRYB_KALKULACJI.AUTORSTWO_MONOGRAFII,
            200,
            1.5,
        ),
        (
            const.DZIEDZINA.NAUKI_MEDYCZNE,
            const.TRYB_KALKULACJI.AUTORSTWO_MONOGRAFII,
            200,
            1,
        ),
        (
            const.DZIEDZINA.NAUKI_TEOLOGICZNE,
            const.TRYB_KALKULACJI.AUTORSTWO_MONOGRAFII,
            80,
            1.25,
        ),
        (
            const.DZIEDZINA.NAUKI_TEOLOGICZNE,
            const.TRYB_KALKULACJI.AUTORSTWO_MONOGRAFII,
            85,
            1,
        ),
        (
            const.DZIEDZINA.NAUKI_TEOLOGICZNE,
            const.TRYB_KALKULACJI.REDAKCJA_MONOGRAFI,
            100,
            1.5,
        ),
        (
            const.DZIEDZINA.NAUKI_TEOLOGICZNE,
            const.TRYB_KALKULACJI.REDAKCJA_MONOGRAFI,
            90,
            1,
        ),
        (
            const.DZIEDZINA.NAUKI_TEOLOGICZNE,
            const.TRYB_KALKULACJI.ROZDZIAL_W_MONOGRAFI,
            50,
            1.5,
        ),
        (
            const.DZIEDZINA.NAUKI_TEOLOGICZNE,
            const.TRYB_KALKULACJI.ROZDZIAL_W_MONOGRAFI,
            55,
            1,
        ),
    ],
)
def test_moznik_dla_monografii(kod, tryb, punktacja, wynik):
    assert mnoznik_dla_monografii(kod, tryb, punktacja) == wynik


def test_moznik_dla_monografii_error():
    with pytest.raises(NotImplementedError):
        mnoznik_dla_monografii(const.DZIEDZINA.NAUKI_TEOLOGICZNE, 65535, 0)


def test_Dyscyplina_Naukowa_mnoznik_dla_monografii():
    assert Dyscyplina_Naukowa(kod="03.05").mnoznik_dla_monografi(
        const.TRYB_KALKULACJI.AUTORSTWO_MONOGRAFII, 200
    )


def test_waliduj_format_kodu_numer():
    waliduj_format_kodu_numer("1.2")

    with pytest.raises(ValidationError):
        waliduj_format_kodu_numer("a.b")

    with pytest.raises(ValidationError):
        waliduj_format_kodu_numer("500.2")
