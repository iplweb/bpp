"""Testy klasyfikacji tytułów (nie-rzucającej), normalizacji i propozycji
skrótu — fundament reconcilera tytułów w imporcie pracowników (Część 3).

Uwaga: baseline (``baseline-sql/baseline.sql``) seeduje ~31 wierszy
``bpp_tytul`` — m.in. ``"doktor habilitowany"``/``"dr hab."``. Dlatego dla
kanonicznego tytułu używamy ``get_or_create`` (a nie ``baker.make``, które
wywaliłoby ``IntegrityError`` na ``unique`` nazwa/skrót), a testy zgadywania
opierają się na NOWYM, długim tytule spoza baseline, żeby kontrolować, że to on
jest najlepszym trafieniem trigramowym.
"""

import pytest
from model_bakery import baker

from bpp.models import Tytul
from import_common.core.tytul import (
    PROG_ZGADYWANIA_TYTULU,
    STATUS_TYTUL_BRAK,
    STATUS_TYTUL_TWARDY,
    STATUS_TYTUL_ZGADYWANIE,
    normalize_tytul,
    sklasyfikuj_tytul,
    zaproponuj_skrot_tytulu,
)

# --- normalize_tytul (czysta funkcja, bez DB) ----------------------------------


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        ("dr hab.", "dr hab"),
        ("Dr. Hab", "dr hab"),
        ("dr hab", "dr hab"),
        ("  DR   HAB.  ", "dr hab"),
        ("prof. dr hab.", "prof dr hab"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_tytul(wejscie, oczekiwane):
    assert normalize_tytul(wejscie) == oczekiwane


# --- zaproponuj_skrot_tytulu (czysta funkcja, bez DB) --------------------------


def test_zaproponuj_skrot_tnie_dluzszy_128():
    dlugi = "x" * 200
    wynik = zaproponuj_skrot_tytulu(dlugi)
    assert len(wynik) == 128
    assert wynik == dlugi[:128]


def test_zaproponuj_skrot_trim_i_pusty():
    assert zaproponuj_skrot_tytulu("  dr hab.  ") == "dr hab."
    assert zaproponuj_skrot_tytulu("") == ""
    assert zaproponuj_skrot_tytulu(None) == ""


# --- sklasyfikuj_tytul: pusty (bez DB — zwraca BRAK przed dotknięciem bazy) -----


def test_pusty_tytul_brak():
    # KRYTYCZNE: pusty tytuł to normalny przypadek — BRAK bez decyzji, bez DB.
    assert sklasyfikuj_tytul("") == (None, STATUS_TYTUL_BRAK, None)
    assert sklasyfikuj_tytul(None) == (None, STATUS_TYTUL_BRAK, None)
    assert sklasyfikuj_tytul("   ") == (None, STATUS_TYTUL_BRAK, None)


# --- sklasyfikuj_tytul: dopasowanie dokładne (norm-exact) ----------------------


@pytest.mark.django_db
def test_norm_exact_warianty():
    # baseline zawiera ten tytuł (id=3); get_or_create jest odporne także na
    # uruchomienie bez baseline (migracje-only) i nie łamie unique.
    t, _ = Tytul.objects.get_or_create(nazwa="doktor habilitowany", skrot="dr hab.")
    for wariant in ("dr hab.", "Dr. Hab", "dr hab"):
        tytul, status, sim = sklasyfikuj_tytul(wariant)
        assert tytul == t, f"wariant={wariant!r}"
        assert status == STATUS_TYTUL_TWARDY
        assert sim is None


@pytest.mark.django_db
def test_norm_exact_po_nazwie():
    t, _ = Tytul.objects.get_or_create(nazwa="doktor habilitowany", skrot="dr hab.")
    tytul, status, sim = sklasyfikuj_tytul("Doktor Habilitowany")
    assert tytul == t
    assert status == STATUS_TYTUL_TWARDY
    assert sim is None


# --- sklasyfikuj_tytul: zgadywanie (trigram >= prog) ---------------------------


@pytest.mark.django_db
def test_zgadywanie_powyzej_progu():
    # Nowy, długi tytuł spoza baseline — literówka na końcu daje trigram bardzo
    # wysoki, ale nie exact; baseline titles są odległe, więc to ten tytuł jest
    # najlepszym trafieniem.
    t = baker.make(
        Tytul,
        nazwa="doktor habilitowany nauk technicznych informatycznych",
        skrot="dr hab. n. tech. inform.",
    )
    tytul, status, sim = sklasyfikuj_tytul(
        "doktor habilitowany nauk technicznych informatycznyc"  # literówka: brak 'h'
    )
    assert tytul == t
    assert status == STATUS_TYTUL_ZGADYWANIE
    assert sim is not None
    assert sim >= PROG_ZGADYWANIA_TYTULU


# --- sklasyfikuj_tytul: śmieć → brak -------------------------------------------


@pytest.mark.django_db
def test_smiec_brak():
    tytul, status, sim = sklasyfikuj_tytul("xyz123")
    assert tytul is None
    assert status == STATUS_TYTUL_BRAK
    assert sim is None
