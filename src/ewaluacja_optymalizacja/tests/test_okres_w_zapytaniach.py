"""Strażnik: listy lat (``rok__in``) też muszą wynikać z ``OKRES_DOMYSLNY``.

Druga — obok filtrów ``rok__gte`` / ``rok__lte`` — kategoria literałów, które
po zmianie okresu liczyłyby po cichu stare lata: wypisane wprost listy
``[2022, 2023, 2024, 2025]`` i ``range(2022, 2026)``. Dochodzi tu pułapka
o jeden: okres to przedział DOMKNIĘTY, a ``range`` ma prawy koniec wyłączny.
"""

from unittest import mock

from ewaluacja_common.const import lata_okresu
from ewaluacja_optymalizacja.views.evaluation_browser.filters import _build_base_filter

OKRES_TESTOWY = (2026, 2029)


def test_lata_okresu_zwraca_przedzial_domkniety():
    # Ostatni rok okresu MUSI się załapać — to jest ten błąd o jeden.
    assert lata_okresu((2022, 2025)) == [2022, 2023, 2024, 2025]
    assert lata_okresu((2026, 2030)) == [2026, 2027, 2028, 2029, 2030]


def test_lata_okresu_czyta_okres_domyslny_przy_wywolaniu():
    assert lata_okresu() == [2022, 2023, 2024, 2025]

    with mock.patch("ewaluacja_common.const.OKRES_DOMYSLNY", OKRES_TESTOWY):
        assert lata_okresu() == [2026, 2027, 2028, 2029]


def test_filtr_przegladarki_publikacji_bierze_lata_z_okresu_domyslnego():
    assert _build_base_filter({})["rok__in"] == [2022, 2023, 2024, 2025]

    with mock.patch("ewaluacja_common.const.OKRES_DOMYSLNY", OKRES_TESTOWY):
        assert _build_base_filter({})["rok__in"] == [2026, 2027, 2028, 2029]
