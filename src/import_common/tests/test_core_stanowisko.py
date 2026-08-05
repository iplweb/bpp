import pytest
from model_bakery import baker

from import_common.core.stanowisko import (
    STATUS_STANOWISKO_BRAK,
    STATUS_STANOWISKO_TWARDY,
    normalize_stanowisko,
    sklasyfikuj_stanowisko,
)


def test_normalize():
    assert normalize_stanowisko("Prof. Uczelni") == "prof uczelni"
    assert normalize_stanowisko(None) == ""


@pytest.mark.django_db
def test_pusty_to_brak():
    assert sklasyfikuj_stanowisko("") == (None, STATUS_STANOWISKO_BRAK, None)


@pytest.mark.django_db
def test_dopasowanie_twarde():
    s = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="adiunkt")
    obj, status, sim = sklasyfikuj_stanowisko("Adiunkt")
    assert obj == s
    assert status == STATUS_STANOWISKO_TWARDY


@pytest.mark.django_db
def test_brak_dopasowania():
    baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="adiunkt")
    obj, status, _ = sklasyfikuj_stanowisko("nieznane xyz")
    assert obj is None
    assert status == STATUS_STANOWISKO_BRAK
