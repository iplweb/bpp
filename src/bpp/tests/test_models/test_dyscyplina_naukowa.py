import pytest
from django.core.exceptions import ValidationError

from bpp import const
from bpp.models import Autor_Dyscyplina, Dyscyplina_Naukowa, waliduj_format_kodu_numer


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


@pytest.mark.parametrize(
    "rodzaj_autora_fixture",
    ["rodzaj_autora_n", "rodzaj_autora_d", "rodzaj_autora_z"],
)
def test_policz_udzialy_rodzaj_ndz(
    autor_jan_nowak, dyscyplina1, rodzaj_autora_fixture, request
):
    rodzaj_autora = request.getfixturevalue(rodzaj_autora_fixture)
    ad = Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=1,
        rok=2020,
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora,
    )
    assert list(ad.policz_udzialy()) == [(dyscyplina1, 1)]
