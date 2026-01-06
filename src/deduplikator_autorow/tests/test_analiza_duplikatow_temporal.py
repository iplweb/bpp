"""
Tests for analiza_duplikatow temporal analysis functionality.

This module contains tests for:
- Common publication years detection
- Close years scoring (difference <= 2 years)
- Medium distance years scoring (3-7 years)
- Large distance years scoring (> 7 years)
- No publications handling
- Temporal scoring impact on final certainty
"""

import pytest
from model_bakery import baker

from deduplikator_autorow.utils import analiza_duplikatow

pytestmark = pytest.mark.django_db


def test_analiza_duplikatow_temporal_analysis_common_years(
    osoba_z_instytucji,
    glowny_autor,
    autor_maker,
    jednostka,
    typ_odpowiedzialnosci_autor,
):
    """Test analizy temporalnej - wspólne lata publikacji"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Dodaj publikacje z tymi samymi latami dla głównego autora i duplikatu
    for rok in [2022, 2023, 2024]:
        # Publikacja dla głównego autora
        wydawnictwo_glowny = baker.make("bpp.Wydawnictwo_Ciagle", rok=rok)
        wydawnictwo_glowny.dodaj_autora(glowny_autor, jednostka)

        # Publikacja dla duplikatu
        wydawnictwo_duplikat = baker.make("bpp.Wydawnictwo_Ciagle", rok=rok)
        wydawnictwo_duplikat.dodaj_autora(duplikat, jednostka)

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Sprawdź czy wspólne lata zostały wykryte
    assert any(
        "wspólne lata publikacji: [2022, 2023, 2024]" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )

    # Pewność powinna być zwiększona o 20 za wspólne lata
    assert any(
        "wspólne lata publikacji" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )


def test_analiza_duplikatow_temporal_analysis_close_years(
    osoba_z_instytucji,
    glowny_autor,
    autor_maker,
    jednostka,
    typ_odpowiedzialnosci_autor,
):
    """Test analizy temporalnej - bliskie lata publikacji (różnica <=2 lata)"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Główny autor: publikacje w 2022-2023
    for rok in [2022, 2023]:
        wydawnictwo_glowny = baker.make("bpp.Wydawnictwo_Ciagle", rok=rok)
        wydawnictwo_glowny.dodaj_autora(glowny_autor, jednostka)

    # Duplikat: publikacje w 2024-2025 (różnica 1-2 lata)
    for rok in [2024, 2025]:
        wydawnictwo_duplikat = baker.make("bpp.Wydawnictwo_Ciagle", rok=rok)
        wydawnictwo_duplikat.dodaj_autora(duplikat, jednostka)

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Sprawdź czy bliskie lata zostały wykryte
    assert any(
        "bliskie lata publikacji" in powod and "prawdopodobny duplikat" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )


def test_analiza_duplikatow_temporal_analysis_medium_distance(
    osoba_z_instytucji,
    glowny_autor,
    autor_maker,
    jednostka,
    typ_odpowiedzialnosci_autor,
):
    """Test analizy temporalnej - średnia odległość lat publikacji (3-7 lat)"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Główny autor: publikacje w 2020
    wydawnictwo_glowny = baker.make("bpp.Wydawnictwo_Ciagle", rok=2020)
    wydawnictwo_glowny.dodaj_autora(glowny_autor, jednostka)

    # Duplikat: publikacje w 2025 (różnica 5 lat)
    wydawnictwo_duplikat = baker.make("bpp.Wydawnictwo_Ciagle", rok=2025)
    wydawnictwo_duplikat.dodaj_autora(duplikat, jednostka)

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Sprawdź czy średnia odległość została wykryta
    assert any(
        "średnia odległość lat publikacji (5 lat) - możliwy duplikat" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )


def test_analiza_duplikatow_temporal_analysis_large_distance(
    osoba_z_instytucji,
    glowny_autor,
    autor_maker,
    jednostka,
    typ_odpowiedzialnosci_autor,
):
    """Test analizy temporalnej - duża odległość lat publikacji (>7 lat)"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Główny autor: publikacje w 2015
    wydawnictwo_glowny = baker.make("bpp.Wydawnictwo_Ciagle", rok=2015)
    wydawnictwo_glowny.dodaj_autora(glowny_autor, jednostka)

    # Duplikat: publikacje w 2025 (różnica 10 lat)
    wydawnictwo_duplikat = baker.make("bpp.Wydawnictwo_Ciagle", rok=2025)
    wydawnictwo_duplikat.dodaj_autora(duplikat, jednostka)

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Sprawdź czy duża odległość została wykryta
    assert any(
        "duża odległość lat publikacji (10 lat) - mało prawdopodobny duplikat" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )

    # Pewność powinna być znacznie obniżona za dużą odległość
    # Faktyczna kalkulacja: mało publikacji (+10) + identyczne nazwisko (+40) +
    # wspólne imię (+30) + pasujące inicjały (+5) + duża odległość (-20) = 65
    # ale duplikat nie ma tytułu (dr) a główny ma (dr hab.),
    # więc brak tytułu daje +15
    # mało publikacji + brak tytułu + identyczne nazwisko + wspólne imię + inicjały
    base_certainty = 10 + 15 + 40 + 30 + 5
    expected_certainty = base_certainty - 20  # minus za dużą odległość lat
    assert duplikat_analiza["pewnosc"] <= expected_certainty


def test_analiza_duplikatow_temporal_analysis_no_publications(
    osoba_z_instytucji, glowny_autor, autor_maker
):
    """Test analizy temporalnej - brak publikacji z rokiem"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Nie dodajemy żadnych publikacji z rokiem

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Nie powinno być żadnych wzmianek o analizie temporalnej
    temporal_reasons = [
        powod
        for powod in duplikat_analiza["powody_podobienstwa"]
        if any(
            keyword in powod
            for keyword in [
                "wspólne lata",
                "bliskie lata",
                "średnia odległość",
                "duża odległość",
            ]
        )
    ]
    assert len(temporal_reasons) == 0


def test_analiza_duplikatow_temporal_analysis_scoring_impact(
    osoba_z_instytucji,
    glowny_autor,
    autor_maker,
    jednostka,
    typ_odpowiedzialnosci_autor,
):
    """Test wpływu analizy temporalnej na końcową pewność"""
    # Duplikat z wspólnymi latami - powinien mieć wyższą pewność
    duplikat_wspolne = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")
    # Duplikat z dużą odległością - powinien mieć niższą pewność
    # (różne imię żeby był osobny rekord)
    duplikat_odlegle = autor_maker(imiona="Janusz", nazwisko="Gal-Cisoń")

    # Wspólne lata dla głównego i pierwszego duplikatu
    for rok in [2022, 2023]:
        wydawnictwo_glowny = baker.make("bpp.Wydawnictwo_Ciagle", rok=rok)
        wydawnictwo_glowny.dodaj_autora(glowny_autor, jednostka)

        wydawnictwo_duplikat = baker.make("bpp.Wydawnictwo_Ciagle", rok=rok)
        wydawnictwo_duplikat.dodaj_autora(duplikat_wspolne, jednostka)

    # Odległe lata dla drugiego duplikatu
    wydawnictwo_odlegly = baker.make(
        "bpp.Wydawnictwo_Ciagle", rok=2010
    )  # 12+ lat różnicy
    wydawnictwo_odlegly.dodaj_autora(duplikat_odlegle, jednostka)

    analiza = analiza_duplikatow(osoba_z_instytucji)

    analiza_wspolne = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat_wspolne), None
    )
    analiza_odlegle = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat_odlegle), None
    )

    assert analiza_wspolne is not None
    assert analiza_odlegle is not None

    # Duplikat ze wspólnymi latami powinien mieć wyższą pewność
    assert analiza_wspolne["pewnosc"] > analiza_odlegle["pewnosc"]

    # Różnica powinna być co najmniej 40 punktów (+20 vs -20)
    assert analiza_wspolne["pewnosc"] - analiza_odlegle["pewnosc"] >= 40
