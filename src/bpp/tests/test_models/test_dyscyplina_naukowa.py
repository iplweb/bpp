import pytest
from django.core.exceptions import ValidationError

from bpp import const
from bpp.models import Dyscyplina_Naukowa, waliduj_format_kodu_numer


def test_Dyscyplina_Naukowa_kod_dziedziny():
    assert Dyscyplina_Naukowa(kod="05.32").kod_dziedziny() == 5


def test_Dyscyplina_Naukowa_dziedzina():
    assert (
        Dyscyplina_Naukowa(kod="03.32").dziedzina()
        == const.DZIEDZINY[const.DZIEDZINA.NAUKI_MEDYCZNE]
    )


def test_waliduj_format_kodu_numer():
    waliduj_format_kodu_numer("1.2")

    with pytest.raises(ValidationError):
        waliduj_format_kodu_numer("a.b")

    with pytest.raises(ValidationError):
        waliduj_format_kodu_numer("500.2")
