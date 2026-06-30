"""Charakteryzacyjne testy dla finderów z utils/finders.py.

Pinują AKTUALNE zachowanie search_author_by_lastname oraz
znajdz_pierwszego_autora_z_duplikatami przed refaktoryzacją (zdjęcie
# noqa: C901). Skupiają się na obserwowalnym kontrakcie zwracanych wartości
(Scientist albo None) oraz na gałęziach wykluczania i wczesnych zwrotów.
"""

import pytest
from model_bakery import baker

from deduplikator_autorow.utils.finders import (
    search_author_by_lastname,
    znajdz_pierwszego_autora_z_duplikatami,
)
from pbn_api.models import OsobaZInstytucji, Scientist


@pytest.fixture
def glowny_z_duplikatem(autor_maker, tytuly):
    """Główny autor z OsobaZInstytucji + duplikat bez własnej OsobaZInstytucji."""
    glowny = autor_maker(imiona="Janusz", nazwisko="Wyszukiwalski")
    scientist = baker.make(Scientist)
    glowny.pbn_uid = scientist
    glowny.save()
    osoba = baker.make(OsobaZInstytucji, personId=scientist)
    duplikat = baker.make("bpp.Autor", imiona="Janusz", nazwisko="Wyszukiwalski")
    return glowny, scientist, osoba, duplikat


# ============================================================================
# search_author_by_lastname
# ============================================================================


def test_search_author_by_lastname_empty_returns_none(db):
    """Pusty / None search_term -> wczesny zwrot None."""
    assert search_author_by_lastname("") is None
    assert search_author_by_lastname(None) is None


def test_search_author_by_lastname_returns_scientist_with_duplicates(
    glowny_z_duplikatem,
):
    """Zwraca Scientist (pbn_uid) autora, który ma duplikaty."""
    glowny, scientist, osoba, duplikat = glowny_z_duplikatem

    result = search_author_by_lastname("Wyszukiwalski")

    assert result == scientist


def test_search_author_by_lastname_excludes_by_pbn_uid(glowny_z_duplikatem):
    """Autor wykluczony (po pbn_uid) nie jest zwracany -> None."""
    glowny, scientist, osoba, duplikat = glowny_z_duplikatem

    result = search_author_by_lastname("Wyszukiwalski", excluded_authors=[scientist])

    assert result is None


def test_search_author_by_lastname_no_match_returns_none(db, autor_maker, tytuly):
    """Brak autorów pasujących do nazwiska -> None."""
    autor_maker(imiona="Jan", nazwisko="Inny")

    result = search_author_by_lastname("NieIstnieje")

    assert result is None


def test_search_author_by_lastname_author_without_osoba_z_instytucji(
    db, autor_maker, tytuly
):
    """Autor z pbn_uid, ale bez OsobaZInstytucji jest pomijany -> None."""
    glowny = autor_maker(imiona="Jan", nazwisko="Bezosobowy")
    scientist = baker.make(Scientist)
    glowny.pbn_uid = scientist
    glowny.save()
    # brak OsobaZInstytucji -> RelatedObjectDoesNotExist -> continue

    result = search_author_by_lastname("Bezosobowy")

    assert result is None


# ============================================================================
# znajdz_pierwszego_autora_z_duplikatami
# ============================================================================


def test_znajdz_pierwszego_returns_scientist_with_duplicates(glowny_z_duplikatem):
    """Zwraca Scientist głównego autora, który ma duplikaty."""
    glowny, scientist, osoba, duplikat = glowny_z_duplikatem

    result = znajdz_pierwszego_autora_z_duplikatami()

    assert result == scientist


def test_znajdz_pierwszego_no_duplicates_returns_none(db, autor_maker, tytuly):
    """Główny autor bez żadnych duplikatów -> None."""
    glowny = autor_maker(imiona="Jan", nazwisko="Samotny")
    scientist = baker.make(Scientist)
    glowny.pbn_uid = scientist
    glowny.save()
    baker.make(OsobaZInstytucji, personId=scientist)

    result = znajdz_pierwszego_autora_z_duplikatami()

    assert result is None


def test_znajdz_pierwszego_excluded_author_returns_none(glowny_z_duplikatem):
    """Wykluczenie głównego autora (Scientist) -> None."""
    glowny, scientist, osoba, duplikat = glowny_z_duplikatem

    result = znajdz_pierwszego_autora_z_duplikatami(excluded_authors=[scientist])

    assert result is None


def test_znajdz_pierwszego_skips_scientist_without_bpp_author(db):
    """Scientist bez rekordu w BPP (brak Autora) jest pomijany -> None."""
    scientist = baker.make(Scientist)
    baker.make(OsobaZInstytucji, personId=scientist)

    result = znajdz_pierwszego_autora_z_duplikatami()

    assert result is None
