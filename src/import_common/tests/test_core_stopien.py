import pytest
from model_bakery import baker

from import_common.core.stopien import (
    STATUS_STOPIEN_BRAK,
    STATUS_STOPIEN_TWARDY,
    normalize_stopien,
    sklasyfikuj_stopien,
    zaproponuj_skrot_stopnia,
)


def test_normalize_usuwa_kropki_i_spacje():
    assert normalize_stopien("st. kpt.") == "st kpt"
    assert normalize_stopien("  Mł.  Bryg. ") == "mł bryg"
    assert normalize_stopien("") == ""
    assert normalize_stopien(None) == ""


def test_zaproponuj_skrot_przycina():
    assert zaproponuj_skrot_stopnia("kpt.") == "kpt."
    assert zaproponuj_skrot_stopnia(None) == ""


@pytest.mark.django_db
def test_pusty_stopien_to_brak():
    assert sklasyfikuj_stopien("") == (None, STATUS_STOPIEN_BRAK, None)
    assert sklasyfikuj_stopien(None) == (None, STATUS_STOPIEN_BRAK, None)


@pytest.mark.django_db
def test_dopasowanie_twarde_mimo_kropek():
    s = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    obj, status, sim = sklasyfikuj_stopien("KPT")
    assert obj == s
    assert status == STATUS_STOPIEN_TWARDY
    assert sim is None


@pytest.mark.django_db
def test_brak_dopasowania_to_brak():
    baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    obj, status, sim = sklasyfikuj_stopien("zupełnie inny xyz")
    assert obj is None
    assert status == STATUS_STOPIEN_BRAK
