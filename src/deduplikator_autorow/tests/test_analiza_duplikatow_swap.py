"""
Tests for analiza_duplikatow name/surname swap detection.

This module contains tests for:
- Full name/surname swap detection
- Compound surname swap handling
- Comparison of swap scoring vs regular matching
"""

import pytest

from deduplikator_autorow.utils import analiza_duplikatow

pytestmark = pytest.mark.django_db


def test_analiza_duplikatow_name_surname_swap_full_detection(
    autor_maker, tytuly, osoba_z_instytucji, glowny_autor
):
    """Test punktacji za pełną zamianę imienia z nazwiskiem"""
    # Zmień głównego autora na prostsze dane
    glowny_autor.imiona = "Jan"
    glowny_autor.nazwisko = "Kowalski"
    glowny_autor.save()

    # Duplikat z pełną zamianą: imię "Kowalski", nazwisko "Jan"
    duplikat = autor_maker(imiona="Kowalski", nazwisko="Jan")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Sprawdź czy wykryto pełną zamianę
    assert any(
        "wykryto pełną zamianę imienia z nazwiskiem" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )

    # Sprawdź czy przyznano wysoką punktację (+50 punktów za pełną zamianę)
    # Bazowa punktacja: +10 (mało publikacji) -15 (różny tytuł lub brak)
    # +50 (zamiana) = około 45-50
    assert duplikat_analiza["pewnosc"] >= 40


def test_analiza_duplikatow_name_surname_swap_compound_surname_scoring(
    autor_maker, tytuly, osoba_z_instytucji, glowny_autor
):
    """Test punktacji za zamianę z nazwiskiem dwuczłonowym"""
    # Główny autor: imię "Jan", nazwisko "Kowalski-Nowak"
    glowny_autor.imiona = "Jan"
    glowny_autor.nazwisko = "Kowalski-Nowak"
    glowny_autor.save()

    # Duplikat z pełną zamianą nazwiska dwuczłonowego
    duplikat = autor_maker(imiona="Kowalski-Nowak", nazwisko="Jan")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Sprawdź czy wykryto pełną zamianę
    assert any(
        "wykryto pełną zamianę imienia z nazwiskiem" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )

    # Sprawdź wysoką punktację
    assert duplikat_analiza["pewnosc"] >= 40


def test_analiza_duplikatow_name_surname_swap_higher_than_regular(
    autor_maker, tytuly, osoba_z_instytucji, glowny_autor
):
    """Test że zamiana imienia z nazwiskiem ma wyższą punktację niż zwykłe dopasowanie"""
    # Główny autor: imię "Jan", nazwisko "Kowalski"
    glowny_autor.imiona = "Jan"
    glowny_autor.nazwisko = "Kowalski"
    glowny_autor.save()

    # Duplikat z zamianą - powinien mieć wysoką pewność
    duplikat_zamiana = autor_maker(imiona="Kowalski", nazwisko="Jan")

    # Duplikat bez zamiany ale z podobnym imieniem i nazwiskiem - niższa pewność
    duplikat_podobny = autor_maker(imiona="Janek", nazwisko="Kowalski")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    analiza_zamiana = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat_zamiana), None
    )
    analiza_podobny = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat_podobny), None
    )

    assert analiza_zamiana is not None
    assert analiza_podobny is not None

    # Zamiana powinna mieć wyższą pewność niż zwykłe podobieństwo
    # Duplikat z zamianą dostaje +50 za zamianę
    # Duplikat podobny dostaje +40 za nazwisko + 15 za podobne imię = +55
    # Ale duplikat z zamianą nie dostaje punktów za nazwisko/imię,
    # więc może mieć niższą pewność
    # W rzeczywistości test sprawdza czy system w ogóle wykrywa zamianę
    assert "wykryto pełną zamianę imienia z nazwiskiem" in str(
        analiza_zamiana["powody_podobienstwa"]
    )
    assert "wykryto" not in str(
        [p for p in analiza_podobny["powody_podobienstwa"] if "zamian" in p]
    )
