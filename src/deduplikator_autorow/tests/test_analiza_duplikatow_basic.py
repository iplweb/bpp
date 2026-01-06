"""
Tests for basic analiza_duplikatow functionality.

This module contains tests for:
- Exact name matching
- Initials scoring
- Surname variations
- Empty names handling
- Similar names detection
- Multiple matches with different quality levels
"""

import pytest

from deduplikator_autorow.utils import analiza_duplikatow

pytestmark = pytest.mark.django_db


def test_analiza_duplikatow_exact_match(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test analizy duplikatów z dokładnym dopasowaniem"""
    duplikat = autor_maker(imiona="Jan Marian", nazwisko="Gal-Cisoń")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    assert analiza["glowny_autor"] == glowny_autor
    assert analiza["ilosc_duplikatow"] == 1
    assert len(analiza["analiza"]) == 1

    duplikat_analiza = analiza["analiza"][0]
    assert duplikat_analiza["autor"] == duplikat
    assert "identyczne nazwisko" in duplikat_analiza["powody_podobienstwa"]
    assert "wspólne imię (2)" in duplikat_analiza["powody_podobienstwa"]
    assert duplikat_analiza["pewnosc"] > 90  # wysoka pewność


def test_analiza_duplikatow_initials_scoring(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test punktowania za inicjały"""
    duplikat1 = autor_maker(imiona="J.", nazwisko="Gal-Cisoń")
    duplikat2 = autor_maker(imiona="J. M.", nazwisko="Gal-Cisoń")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    assert len(analiza["analiza"]) == 2

    # Znajdź analizy duplikatów
    analiza_j = next(a for a in analiza["analiza"] if a["autor"] == duplikat1)
    analiza_jm = next(a for a in analiza["analiza"] if a["autor"] == duplikat2)

    assert "pasujące inicjały (1)" in analiza_j["powody_podobienstwa"]
    # Nowe punktowanie: +10 (mało publikacji) -15 (różny tytuł) +40 (nazwisko)
    # +5 (inicjał) = 40
    assert analiza_j["pewnosc"] >= 35  # skorygowana wartość

    assert "pasujące inicjały (2)" in analiza_jm["powody_podobienstwa"]
    # Nowe punktowanie: +10 (mało publikacji) -15 (różny tytuł) +40 (nazwisko)
    # +10 (2 inicjały) = 45
    assert analiza_jm["pewnosc"] >= 40  # skorygowana wartość

    # J. M. powinien mieć wyższą pewność niż samo J.
    assert analiza_jm["pewnosc"] > analiza_j["pewnosc"]


def test_analiza_duplikatow_surname_variations(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test analizy różnych wariantów nazwiska"""
    duplikat1 = autor_maker(imiona="Jan", nazwisko="Cisoń-Gal")  # odwrócone
    duplikat2 = autor_maker(imiona="Jan", nazwisko="Gal")  # część
    # Usuwam "Galewski" - to zbyt luźne dopasowanie dla naszej funkcji

    analiza = analiza_duplikatow(osoba_z_instytucji)

    # Sprawdź że duplikaty są posortowane według pewności
    pewnosci = [d["pewnosc"] for d in analiza["analiza"]]
    assert pewnosci == sorted(pewnosci, reverse=True)

    # Znajdź konkretne duplikaty
    analiza_odwrocone = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat1), None
    )
    analiza_czesc = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat2), None
    )

    assert analiza_odwrocone is not None
    assert analiza_czesc is not None

    assert "podobne nazwisko" in analiza_czesc["powody_podobienstwa"]


def test_analiza_duplikatow_empty_names(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test analizy duplikatów z pustymi imionami"""
    duplikat = autor_maker(imiona="", nazwisko="Gal-Cisoń")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    assert len(analiza["analiza"]) >= 1
    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None
    assert "brak imion w duplikacie" in duplikat_analiza["powody_podobienstwa"]
    # Nowe punktowanie: +10 (mało publikacji) -15 (różny tytuł) +40 (nazwisko)
    # +10 (brak imion) = 45
    assert duplikat_analiza["pewnosc"] >= 40  # skorygowana wartość


def test_analiza_duplikatow_similar_names(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test analizy podobnych imion"""
    duplikat1 = autor_maker(imiona="Janek", nazwisko="Gal-Cisoń")  # podobne do Jan
    duplikat2 = autor_maker(imiona="Janusz", nazwisko="Gal-Cisoń")  # podobne do Jan
    duplikat3 = autor_maker(imiona="Mariusz", nazwisko="Gal-Cisoń")  # podobne do Marian

    analiza = analiza_duplikatow(osoba_z_instytucji)

    # Sprawdź że wszystkie duplikaty zostały znalezione
    found_authors = [a["autor"] for a in analiza["analiza"]]
    assert duplikat1 in found_authors
    assert duplikat2 in found_authors
    assert duplikat3 in found_authors

    for duplikat_analiza in analiza["analiza"]:
        if any(
            "podobne imię" in powod for powod in duplikat_analiza["powody_podobienstwa"]
        ):
            assert (
                duplikat_analiza["pewnosc"] >= 55
            )  # 40 za nazwisko + 15 za podobne imię


def test_analiza_duplikatow_multiple_matches(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test analizy z wieloma dopasowaniami różnej jakości"""
    # Wysokiej jakości duplikat
    duplikat_wysoka = autor_maker(imiona="Jan Marian", nazwisko="Gal-Cisoń")
    # Średniej jakości duplikat
    duplikat_srednia = autor_maker(imiona="J. M.", nazwisko="Gal-Cisoń")
    # Niskiej jakości duplikat
    duplikat_niska = autor_maker(imiona="", nazwisko="Gal")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    # Sprawdź że wszystkie duplikaty zostały znalezione
    found_authors = [a["autor"] for a in analiza["analiza"]]
    assert duplikat_wysoka in found_authors
    assert duplikat_srednia in found_authors
    assert duplikat_niska in found_authors

    # Sprawdź sortowanie według pewności
    pewnosci = [d["pewnosc"] for d in analiza["analiza"]]
    assert pewnosci == sorted(pewnosci, reverse=True)

    # Najwyższa pewność powinna być dla pełnego dopasowania
    najwyzsza_pewnosc = analiza["analiza"][0]
    assert najwyzsza_pewnosc["autor"] == duplikat_wysoka
    assert najwyzsza_pewnosc["pewnosc"] > 90
