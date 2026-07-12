import pytest
from model_bakery import baker

from import_common.core.jednostka import (
    STATUS_JEDNOSTKA_BRAK,
    STATUS_JEDNOSTKA_TWARDY,
    STATUS_JEDNOSTKA_ZGADYWANIE,
    sklasyfikuj_jednostke_niepelna,
)


@pytest.mark.django_db
def test_pusty_fragment_to_brak():
    assert sklasyfikuj_jednostke_niepelna("") == (None, STATUS_JEDNOSTKA_BRAK, None)


@pytest.mark.django_db
def test_dokladna_nazwa_to_twardy():
    j = baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    obj, status, _ = sklasyfikuj_jednostke_niepelna("Wydział Medyczny")
    assert obj == j
    assert status == STATUS_JEDNOSTKA_TWARDY


@pytest.mark.django_db
def test_fragment_trafia_przez_icontains_jako_zgadywanie():
    j = baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    obj, status, _ = sklasyfikuj_jednostke_niepelna("Medyczny")
    assert obj == j
    assert status == STATUS_JEDNOSTKA_ZGADYWANIE


@pytest.mark.django_db
def test_brak_trafienia():
    baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    obj, status, _ = sklasyfikuj_jednostke_niepelna("Kompletnie inny fragment zzz")
    assert obj is None
    assert status == STATUS_JEDNOSTKA_BRAK


@pytest.mark.django_db
def test_fallback_trigram_gdy_brak_substring():
    # Fragment NIE jest substringiem (icontains puste), ale trigramowo bliski —
    # gałąź fallback woła sklasyfikuj_jednostke (trigram), więc zamiast twardego
    # BRAK dostajemy zgadywanie (albo brak), NIGDY crash (spec §6.1 „0 → trigram").
    baker.make("bpp.Jednostka", nazwa="Instytut Medyczny", widoczna=True)
    obj, status, _ = sklasyfikuj_jednostke_niepelna("Instytut Medycyzny")
    assert status in (STATUS_JEDNOSTKA_ZGADYWANIE, STATUS_JEDNOSTKA_BRAK)
    if status == STATUS_JEDNOSTKA_ZGADYWANIE:
        assert obj is not None
