"""Fikstury testów modułu ewaluacja_optymalizacja."""

import pytest

#: Rok „bieżący" dla testów tej aplikacji — dane testowe leżą w 2022–2025.
ROK_TESTOWY = 2024


@pytest.fixture(autouse=True)
def okres_domyslny_2022_2025(monkeypatch):
    """Okres domyślny = 2022–2025 (zamiast okresu zawierającego dzisiejszą
    datę), bo dane w testach tej aplikacji leżą w latach 2022–2025.

    Gdy tabela okresów jest pusta (np. po TRUNCATE z ``transactional_db``),
    odtwarza okresy z migracji ``ewaluacja_common.0006``."""
    from ewaluacja_common import okres as okres_common

    oryginal = okres_common.okres_domyslny

    def okres_domyslny(rok=None):
        rok = ROK_TESTOWY if rok is None else rok
        wynik = oryginal(rok)
        if wynik is None:
            from ewaluacja_common.models import OkresEwaluacji

            OkresEwaluacji.objects.get_or_create(rok_od=2022, defaults={"rok_do": 2025})
            OkresEwaluacji.objects.get_or_create(rok_od=2026, defaults={"rok_do": 2030})
            wynik = oryginal(rok)
        return wynik

    monkeypatch.setattr(okres_common, "okres_domyslny", okres_domyslny)


@pytest.fixture
def okres_2022(db):
    from ewaluacja_common.models import OkresEwaluacji

    return OkresEwaluacji.objects.get_or_create(rok_od=2022, defaults={"rok_do": 2025})[
        0
    ]


@pytest.fixture
def okres_2026(db):
    from ewaluacja_common.models import OkresEwaluacji

    return OkresEwaluacji.objects.get_or_create(rok_od=2026, defaults={"rok_do": 2030})[
        0
    ]


@pytest.fixture
def okresy_ewaluacji(okres_2022, okres_2026):
    """Oba okresy z migracji ``ewaluacja_common.0006`` — dla testów z live
    serverem (osobny proces: nie widzi monkeypatcha, a TRUNCATE po
    poprzednim teście ``transactional_db`` czyści tabelę okresów)."""
    return okres_2022, okres_2026
