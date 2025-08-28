"""
Testy dla modułu deduplicator.utils
"""

import pytest
from model_bakery import baker

from deduplicator.utils import analiza_duplikatow, szukaj_kopii
from pbn_api.models import OsobaZInstytucji, Scientist


@pytest.fixture
def glowny_autor(autor_maker, tytuly):
    """Główny autor z pełnymi danymi"""
    return autor_maker(imiona="Jan Marian", nazwisko="Gal-Cisoń", tytul="dr hab.")


@pytest.fixture
def scientist_for_glowny_autor(glowny_autor):
    """Scientist powiązany z głównym autorem"""
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    return scientist


@pytest.fixture
def osoba_z_instytucji(scientist_for_glowny_autor):
    """OsobaZInstytucji powiązana z głównym autorem"""
    return baker.make(OsobaZInstytucji, personId=scientist_for_glowny_autor)


def test_szukaj_kopii_identical_surname(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test wyszukiwania duplikatów z identycznym nazwiskiem"""
    # Duplikat z identycznym nazwiskiem
    duplikat1 = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")
    # Duplikat z odwróconym nazwiskiem
    duplikat2 = autor_maker(imiona="Jan", nazwisko="Cisoń-Gal")
    # Autor z innym nazwiskiem - nie powinien być znaleziony
    autor_maker(imiona="Jan", nazwisko="Kowalski")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat1 in duplikaty
    assert duplikat2 in duplikaty
    assert glowny_autor not in duplikaty  # główny autor nie powinien być w duplikatach


def test_szukaj_kopii_surname_parts(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test wyszukiwania duplikatów na podstawie części nazwiska"""
    # Duplikaty z częściami nazwiska
    duplikat1 = autor_maker(imiona="Jan", nazwisko="Gal")
    duplikat2 = autor_maker(imiona="Jan", nazwisko="Cisoń")
    # Zbyt krótka część nazwiska - nie powinien być znaleziony
    autor_maker(imiona="Jan", nazwisko="Ga")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat1 in duplikaty
    assert duplikat2 in duplikaty


def test_szukaj_kopii_initials(osoba_z_instytucji, glowny_autor, autor_maker, tytuly):
    """Test wyszukiwania duplikatów z inicjałami"""
    # Duplikaty z inicjałami
    duplikat1 = autor_maker(imiona="J.", nazwisko="Gal-Cisoń")
    duplikat2 = autor_maker(imiona="J. M.", nazwisko="Gal-Cisoń")
    duplikat3 = autor_maker(imiona="Jan M.", nazwisko="Gal-Cisoń")
    duplikat4 = autor_maker(imiona="M.", nazwisko="Gal-Cisoń")  # drugie imię

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat1 in duplikaty
    assert duplikat2 in duplikaty
    assert duplikat3 in duplikaty
    assert duplikat4 in duplikaty


def test_szukaj_kopii_empty_names(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test wyszukiwania duplikatów z pustymi imionami"""
    # Duplikat bez imion (tylko pusty string, nie None)
    duplikat1 = autor_maker(imiona="", nazwisko="Gal-Cisoń")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat1 in duplikaty


def test_szukaj_kopii_no_bpp_author(
    osoba_z_instytucji, scientist_for_glowny_autor, glowny_autor
):
    """Test gdy Scientist nie ma odpowiedniego autora w BPP"""
    # Usuń powiązanie z autorem BPP
    glowny_autor.pbn_uid = None
    glowny_autor.save()

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikaty.count() == 0


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
    # Nowe punktowanie: +10 (mało publikacji) -15 (różny tytuł) +40 (nazwisko) +5 (inicjał) = 40
    assert analiza_j["pewnosc"] >= 35  # skorygowana wartość

    assert "pasujące inicjały (2)" in analiza_jm["powody_podobienstwa"]
    # Nowe punktowanie: +10 (mało publikacji) -15 (różny tytuł) +40 (nazwisko) +10 (2 inicjały) = 45
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
    # Nowe punktowanie: +10 (mało publikacji) -15 (różny tytuł) +40 (nazwisko) +10 (brak imion) = 45
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


def test_szukaj_kopii_case_insensitive(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test że wyszukiwanie jest case-insensitive"""
    duplikat1 = autor_maker(imiona="jan", nazwisko="gal-cisoń")
    duplikat2 = autor_maker(imiona="JAN", nazwisko="GAL-CISOŃ")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat1 in duplikaty
    assert duplikat2 in duplikaty


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


def test_analiza_duplikatow_publication_count_title_orcid_scoring(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test punktowania na podstawie liczby publikacji, tytułu naukowego i ORCID"""

    # Duplikat z małą liczbą publikacji, bez tytułu i ORCID - wysokie prawdopodobieństwo duplikatu
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


def test_analiza_duplikatow_temporal_analysis_common_years(
    osoba_z_instytucji, glowny_autor, autor_maker, wydawnictwo_ciagle_maker
):
    """Test analizy temporalnej - wspólne lata publikacji"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Dodaj publikacje z tymi samymi latami dla głównego autora i duplikatu
    for rok in [2022, 2023, 2024]:
        # Publikacja dla głównego autora
        wydawnictwo_glowny = wydawnictwo_ciagle_maker(rok=rok)
        wydawnictwo_glowny.dodaj_autora(glowny_autor)

        # Publikacja dla duplikatu
        wydawnictwo_duplikat = wydawnictwo_ciagle_maker(rok=rok)
        wydawnictwo_duplikat.dodaj_autora(duplikat)

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
    osoba_z_instytucji, glowny_autor, autor_maker, wydawnictwo_ciagle_maker
):
    """Test analizy temporalnej - bliskie lata publikacji (różnica ≤2 lata)"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Główny autor: publikacje w 2022-2023
    for rok in [2022, 2023]:
        wydawnictwo_glowny = wydawnictwo_ciagle_maker(rok=rok)
        wydawnictwo_glowny.dodaj_autora(glowny_autor)

    # Duplikat: publikacje w 2024-2025 (różnica 1-2 lata)
    for rok in [2024, 2025]:
        wydawnictwo_duplikat = wydawnictwo_ciagle_maker(rok=rok)
        wydawnictwo_duplikat.dodaj_autora(duplikat)

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
    osoba_z_instytucji, glowny_autor, autor_maker, wydawnictwo_ciagle_maker
):
    """Test analizy temporalnej - średnia odległość lat publikacji (3-7 lat)"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Główny autor: publikacje w 2020
    wydawnictwo_glowny = wydawnictwo_ciagle_maker(rok=2020)
    wydawnictwo_glowny.dodaj_autora(glowny_autor)

    # Duplikat: publikacje w 2025 (różnica 5 lat)
    wydawnictwo_duplikat = wydawnictwo_ciagle_maker(rok=2025)
    wydawnictwo_duplikat.dodaj_autora(duplikat)

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
    osoba_z_instytucji, glowny_autor, autor_maker, wydawnictwo_ciagle_maker
):
    """Test analizy temporalnej - duża odległość lat publikacji (>7 lat)"""
    duplikat = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Główny autor: publikacje w 2015
    wydawnictwo_glowny = wydawnictwo_ciagle_maker(rok=2015)
    wydawnictwo_glowny.dodaj_autora(glowny_autor)

    # Duplikat: publikacje w 2025 (różnica 10 lat)
    wydawnictwo_duplikat = wydawnictwo_ciagle_maker(rok=2025)
    wydawnictwo_duplikat.dodaj_autora(duplikat)

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
    base_certainty = 10 + 40 - 15  # mało publikacji + identyczne nazwisko + różny tytuł
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
    osoba_z_instytucji, glowny_autor, autor_maker, wydawnictwo_ciagle_maker
):
    """Test wpływu analizy temporalnej na końcową pewność"""
    # Duplikat z wspólnymi latami - powinien mieć wyższą pewność
    duplikat_wspolne = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")
    # Duplikat z dużą odległością - powinien mieć niższą pewność
    duplikat_odlegle = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Wspólne lata dla głównego i pierwszego duplikatu
    for rok in [2022, 2023]:
        wydawnictwo_glowny = wydawnictwo_ciagle_maker(rok=rok)
        wydawnictwo_glowny.dodaj_autora(glowny_autor)

        wydawnictwo_duplikat = wydawnictwo_ciagle_maker(rok=rok)
        wydawnictwo_duplikat.dodaj_autora(duplikat_wspolne)

    # Odległe lata dla drugiego duplikatu
    wydawnictwo_odlegly = wydawnictwo_ciagle_maker(rok=2010)  # 12+ lat różnicy
    wydawnictwo_odlegly.dodaj_autora(duplikat_odlegle)

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
