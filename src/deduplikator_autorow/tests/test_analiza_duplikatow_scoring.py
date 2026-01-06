"""
Tests for analiza_duplikatow scoring functionality.

This module contains tests for:
- Publication count scoring
- Academic title scoring
- ORCID scoring and matching
"""

import pytest

from deduplikator_autorow.utils import analiza_duplikatow

pytestmark = pytest.mark.django_db


def test_analiza_duplikatow_publication_count_title_orcid_scoring(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test punktowania na podstawie liczby publikacji, tytułu naukowego i ORCID"""

    # Duplikat z małą liczbą publikacji, bez tytułu i ORCID
    # - wysokie prawdopodobieństwo duplikatu
    # Nie podajemy tytul=None, bo autor_maker tego nie obsługuje - po prostu pomijamy
    duplikat_prawdopodobny = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń", orcid=None)
    # Ręcznie ustawiamy tytul na None
    duplikat_prawdopodobny.tytul = None
    duplikat_prawdopodobny.save()

    # Duplikat z tytułem ale bez ORCID - średnie prawdopodobieństwo
    duplikat_z_tytulem = autor_maker(
        imiona="Jan", nazwisko="Gal-Cisoń", tytul="dr", orcid=None
    )

    # Duplikat z ORCID ale różnym od głównego - bardzo małe prawdopodobieństwo
    duplikat_z_orcid = autor_maker(
        imiona="Jan", nazwisko="Gal-Cisoń", tytul="dr hab.", orcid="0000-0000-0000-0001"
    )

    # Ustawiamy ORCID dla głównego autora
    if not glowny_autor.orcid:
        glowny_autor.orcid = "0000-0000-0000-0002"
        glowny_autor.save()

    analiza = analiza_duplikatow(osoba_z_instytucji)

    # Znajdź analizy poszczególnych duplikatów
    analiza_prawdopodobna = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat_prawdopodobny), None
    )
    analiza_z_tytulem = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat_z_tytulem), None
    )
    analiza_z_orcid = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat_z_orcid), None
    )

    assert analiza_prawdopodobna is not None
    assert analiza_z_tytulem is not None
    assert analiza_z_orcid is not None

    # Sprawdź, czy duplikat bez tytułu i ORCID ma wyższe prawdopodobieństwo
    assert (
        "brak tytułu naukowego - prawdopodobny duplikat"
        in analiza_prawdopodobna["powody_podobienstwa"]
    )
    assert (
        "brak ORCID - prawdopodobny duplikat"
        in analiza_prawdopodobna["powody_podobienstwa"]
    )

    # Sprawdź, że duplikat z różnym ORCID ma znacznie obniżoną pewność
    assert "różny ORCID - to różni autorzy" in analiza_z_orcid["powody_podobienstwa"]
    assert analiza_z_orcid["pewnosc"] < analiza_prawdopodobna["pewnosc"]

    # Duplikat bez tytułu i ORCID powinien mieć najwyższą pewność
    assert analiza_prawdopodobna["pewnosc"] > analiza_z_tytulem["pewnosc"]
    assert analiza_prawdopodobna["pewnosc"] > analiza_z_orcid["pewnosc"]
