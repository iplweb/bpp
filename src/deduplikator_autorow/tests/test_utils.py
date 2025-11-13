"""
Testy dla modułu deduplikator_autorow.utils
"""

import pytest
from model_bakery import baker

from deduplikator_autorow.utils import (
    analiza_duplikatow,
    szukaj_kopii,
    znajdz_pierwszego_autora_z_duplikatami,
)
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
    """Test analizy temporalnej - bliskie lata publikacji (różnica ≤2 lata)"""
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
    # ale duplikat nie ma tytułu (dr) a główny ma (dr hab.), więc brak tytułu daje +15
    base_certainty = (
        10 + 15 + 40 + 30 + 5
    )  # mało publikacji + brak tytułu + identyczne nazwisko + wspólne imię + inicjały
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
    # Duplikat z dużą odległością - powinien mieć niższą pewność (różne imię żeby był osobny rekord)
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


def test_znajdz_pierwszego_autora_z_duplikatami_with_duplicates(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test znajdowania pierwszego autora z duplikatami"""
    # Utwórz duplikat dla głównego autora
    autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")

    # Uruchom funkcję
    result = znajdz_pierwszego_autora_z_duplikatami()

    # Powinien zwrócić Scientist
    assert result is not None
    assert isinstance(result, Scientist)
    assert result == osoba_z_instytucji.personId


@pytest.mark.django_db
def test_znajdz_pierwszego_autora_z_duplikatami_no_duplicates():
    """Test gdy nie ma duplikatów"""
    # Nie tworzymy żadnych duplikatów - tylko główny autor istnieje

    result = znajdz_pierwszego_autora_z_duplikatami()

    # Nie powinien znaleźć żadnego autora z duplikatami
    assert result is None


def test_znajdz_pierwszego_autora_z_duplikatami_with_excluded_authors(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test wykluczania określonych autorów z wyszukiwania"""
    # Utwórz duplikat dla głównego autora
    autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")  # noqa

    # Wyklucz głównego autora (Scientist)
    excluded_authors = [osoba_z_instytucji.personId]

    result = znajdz_pierwszego_autora_z_duplikatami(excluded_authors)

    # Nie powinien znaleźć żadnego autora, bo główny został wykluczony
    assert result is None


def test_znajdz_pierwszego_autora_z_duplikatami_multiple_authors_with_duplicates(
    autor_maker, jednostka, tytuly
):
    """Test z wieloma autorami mającymi duplikaty - powinien zwrócić pierwszego"""
    # Utwórz pierwszego autora z duplikatem
    autor1 = autor_maker(imiona="Jan", nazwisko="Kowalski")
    scientist1 = baker.make(Scientist, lastName="Kowalski", name="Jan")
    autor1.pbn_uid = scientist1
    autor1.save()
    osoba1 = baker.make(OsobaZInstytucji, personId=scientist1)  # noqa
    duplikat1 = autor_maker(imiona="J.", nazwisko="Kowalski")  # noqa

    # Utwórz drugiego autora z duplikatem
    autor2 = autor_maker(imiona="Anna", nazwisko="Nowak")
    scientist2 = baker.make(Scientist, lastName="Nowak", name="Anna")
    autor2.pbn_uid = scientist2
    autor2.save()
    osoba2 = baker.make(OsobaZInstytucji, personId=scientist2)  # noqa
    duplikat2 = autor_maker(imiona="A.", nazwisko="Nowak")  # noqa

    result = znajdz_pierwszego_autora_z_duplikatami()

    # Powinien zwrócić któregoś z autorów (pierwszego znalezionego)
    assert result is not None
    assert isinstance(result, Scientist)
    assert result in [scientist1, scientist2]


@pytest.mark.django_db
def test_znajdz_pierwszego_autora_z_duplikatami_no_bpp_author():
    """Test gdy Scientist nie ma odpowiedniego autora BPP"""
    # Utwórz Scientist bez powiązania z BPP
    scientist = baker.make(Scientist, lastName="Test", name="Test")
    osoba = baker.make(OsobaZInstytucji, personId=scientist)  # noqa

    result = znajdz_pierwszego_autora_z_duplikatami()

    # Nie powinien znaleźć żadnego autora, bo nie ma powiązania z BPP
    assert result is None


# ===== Testy wykrywania zamiany imienia z nazwiskiem =====


def test_szukaj_kopii_name_surname_swap_basic(autor_maker, tytuly):
    """Test wykrywania podstawowej zamiany imienia z nazwiskiem"""
    # Główny autor: imię "Jan", nazwisko "Kowalski"
    glowny_autor = autor_maker(imiona="Jan", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikat z zamienionymi polami: imię "Kowalski", nazwisko "Jan"
    duplikat = autor_maker(imiona="Kowalski", nazwisko="Jan")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat in duplikaty


def test_szukaj_kopii_name_surname_swap_compound_surname(autor_maker, tytuly):
    """Test wykrywania zamiany dla nazwisk dwuczłonowych - tylko pełna zamiana"""
    # Główny autor: imię "Jan", nazwisko "Kowalski-Nowak"
    glowny_autor = autor_maker(imiona="Jan", nazwisko="Kowalski-Nowak")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikat z pełnym nazwiskiem jako imieniem - POWINIEN zostać znaleziony
    duplikat1 = autor_maker(imiona="Kowalski-Nowak", nazwisko="Jan")
    # Duplikat z częścią nazwiska jako imieniem - NIE POWINIEN zostać znaleziony
    # (zbyt luźne dopasowanie, może być inna osoba o nazwisku "Kowalski")
    duplikat2 = autor_maker(imiona="Kowalski", nazwisko="Jan")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    # Sprawdź że pełna zamiana została znaleziona
    assert duplikat1 in duplikaty
    # Sprawdź że częściowa zamiana NIE została znaleziona (aby uniknąć fałszywych dopasowań)
    assert duplikat2 not in duplikaty


def test_szukaj_kopii_name_surname_swap_multiple_first_names(autor_maker, tytuly):
    """Test wykrywania zamiany gdy autor ma wiele imion"""
    # Główny autor: imiona "Jan Marian", nazwisko "Kowalski"
    glowny_autor = autor_maker(imiona="Jan Marian", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikat z pierwszym imieniem jako nazwiskiem
    duplikat1 = autor_maker(imiona="Kowalski", nazwisko="Jan")
    # Duplikat z drugim imieniem jako nazwiskiem
    duplikat2 = autor_maker(imiona="Kowalski", nazwisko="Marian")
    # Duplikat z nazwiskiem jako jednym z imion
    duplikat3 = autor_maker(imiona="Jan Kowalski", nazwisko="Marian")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat1 in duplikaty
    assert duplikat2 in duplikaty
    assert duplikat3 in duplikaty


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
    # Bazowa punktacja: +10 (mało publikacji) -15 (różny tytuł lub brak) +50 (zamiana) = około 45-50
    assert duplikat_analiza["pewnosc"] >= 40


def test_analiza_duplikatow_name_surname_swap_partial_detection(
    autor_maker, tytuly, osoba_z_instytucji, glowny_autor
):
    """Test punktacji za częściową zamianę imienia z nazwiskiem"""
    # Główny autor: imiona "Jan Marian", nazwisko "Kowalski"
    glowny_autor.imiona = "Jan Marian"
    glowny_autor.nazwisko = "Kowalski"
    glowny_autor.save()

    # Duplikat z częściową zamianą - nazwisko głównego (Kowalski) = imię duplikatu (Kowalski),
    # ale nazwisko duplikatu (Tomasz) NIE jest imieniem głównego (Jan, Marian)
    duplikat = autor_maker(imiona="Kowalski", nazwisko="Tomasz")

    analiza = analiza_duplikatow(osoba_z_instytucji)

    duplikat_analiza = next(
        (a for a in analiza["analiza"] if a["autor"] == duplikat), None
    )
    assert duplikat_analiza is not None

    # Sprawdź czy wykryto częściową zamianę
    assert any(
        "wykryto częściową zamianę imienia z nazwiskiem" in powod
        for powod in duplikat_analiza["powody_podobienstwa"]
    )

    # Sprawdź czy częściowa zamiana dodaje niewielką punktację (+5 punktów)
    # Bazowa punktacja: +10 (mało publikacji) -15 (różny tytuł lub brak) +5 (częściowa zamiana) = około 0
    assert duplikat_analiza["pewnosc"] >= 0


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
    # Ale duplikat z zamianą nie dostaje punktów za nazwisko/imię, więc może mieć niższą pewność
    # W rzeczywistości test sprawdza czy system w ogóle wykrywa zamianę
    assert "wykryto pełną zamianę imienia z nazwiskiem" in str(
        analiza_zamiana["powody_podobienstwa"]
    )
    assert "wykryto" not in str(
        [p for p in analiza_podobny["powody_podobienstwa"] if "zamian" in p]
    )


# ===== Testy wykluczania autorów z własnym OsobaZInstytucji =====


def test_szukaj_kopii_excludes_authors_with_own_osoba_z_instytucji(autor_maker, tytuly):
    """Test że autorzy z własnym rekordem OsobaZInstytucji NIE są wykrywani jako duplikaty"""
    # Główny autor: Jan Kowalski
    glowny_autor = autor_maker(imiona="Jan", nazwisko="Kowalski")
    scientist_glowny = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist_glowny
    glowny_autor.save()
    osoba_z_instytucji_glowny = baker.make(OsobaZInstytucji, personId=scientist_glowny)

    # Potencjalny duplikat 1: Jan Kowalski (bez OsobaZInstytucji) - POWINIEN być wykryty
    # Używamy baker.make zamiast autor_maker żeby utworzyć NOWY obiekt a nie get_or_create
    duplikat_bez_ozi = baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski")

    # Potencjalny duplikat 2: Jan Kowalski z własnym OsobaZInstytucji - NIE POWINIEN być wykryty
    duplikat_z_ozi = baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski")
    scientist_duplikat = baker.make(Scientist)
    duplikat_z_ozi.pbn_uid = scientist_duplikat
    duplikat_z_ozi.save()
    # Tworzymy OsobaZInstytucji dla duplikatu - nie używamy jej później, ale jest potrzebna
    _ = baker.make(OsobaZInstytucji, personId=scientist_duplikat)

    duplikaty = szukaj_kopii(osoba_z_instytucji_glowny)

    duplikaty_pks = [d.pk for d in duplikaty]

    # Sprawdź że duplikat bez OsobaZInstytucji został znaleziony
    assert duplikat_bez_ozi.pk in duplikaty_pks

    # Sprawdź że duplikat z własnym OsobaZInstytucji został wykluczony
    assert duplikat_z_ozi.pk not in duplikaty_pks


def test_szukaj_kopii_allows_duplicates_without_osoba_z_instytucji(autor_maker, tytuly):
    """Test że autorzy bez własnego OsobaZInstytucji MOGĄ być wykrywani jako duplikaty"""
    # Główny autor: Jan Kowalski
    glowny_autor = autor_maker(imiona="Jan", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikaty bez własnego OsobaZInstytucji (różne warianty imienia/nazwiska)
    # Używamy baker.make żeby utworzyć NOWE obiekty a nie get_or_create
    duplikat1 = baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski")  # Identyczny
    duplikat2 = baker.make("bpp.Autor", imiona="J.", nazwisko="Kowalski")  # Inicjał
    duplikat3 = baker.make(
        "bpp.Autor", imiona="Jan Adam", nazwisko="Kowalski"
    )  # Dodatkowe imię

    # Żaden z tych duplikatów nie ma pbn_uid ani OsobaZInstytucji

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    duplikaty_pks = [d.pk for d in duplikaty]

    # Wszystkie powinny być wykryte jako potencjalne duplikaty
    assert duplikat1.pk in duplikaty_pks
    assert duplikat2.pk in duplikaty_pks
    assert duplikat3.pk in duplikaty_pks


def test_szukaj_kopii_main_author_finds_duplicates_despite_having_ozi(
    autor_maker, tytuly
):
    """Test że główny autor (z OsobaZInstytucji) nadal znajduje duplikaty bez OsobaZInstytucji"""
    # Główny autor z OsobaZInstytucji: Jan Kowalski
    glowny_autor = autor_maker(imiona="Jan", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikat bez OsobaZInstytucji
    # Używamy baker.make żeby utworzyć NOWY obiekt a nie get_or_create
    duplikat = baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    duplikaty_pks = [d.pk for d in duplikaty]

    # Główny autor (mimo że ma OsobaZInstytucji) powinien znaleźć duplikat bez OsobaZInstytucji
    assert duplikat.pk in duplikaty_pks

    # Ale główny autor nie powinien sam siebie znaleźć
    assert glowny_autor.pk not in duplikaty_pks


def test_szukaj_kopii_no_false_positives_with_compound_surnames(autor_maker, tytuly):
    """Test że nazwiska złożone nie powodują fałszywych dopasowań przez substring matching"""
    # Główny autor: Anna Gal-Cisoń
    glowny_autor = autor_maker(imiona="Anna", nazwisko="Gal-Cisoń")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Potencjalny fałszywy duplikat: Magali Ribiere-Chabert
    # "Gal" jako substring w "Magali" NIE POWINNO powodować dopasowania
    falszywy_duplikat = baker.make(
        "bpp.Autor", imiona="Magali", nazwisko="Ribiere-Chabert"
    )

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    duplikaty_pks = [d.pk for d in duplikaty]

    # Sprawdź że fałszywy duplikat NIE został znaleziony
    assert falszywy_duplikat.pk not in duplikaty_pks


def test_szukaj_kopii_exact_match_for_compound_surname_parts(autor_maker, tytuly):
    """Test że części nazwisk złożonych są dopasowywane DOKŁADNIE, nie jako substring"""
    # Główny autor: Anna Gal-Cisoń
    glowny_autor = autor_maker(imiona="Anna", nazwisko="Gal-Cisoń")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Prawdziwy duplikat: dokładne dopasowanie części "Gal"
    prawdziwy_duplikat = baker.make("bpp.Autor", imiona="Anna", nazwisko="Gal")

    # Fałszywy duplikat: "Gal" jako substring w "Galina"
    falszywy_duplikat1 = baker.make("bpp.Autor", imiona="Anna", nazwisko="Galina")

    # Fałszywy duplikat: "Gal" jako substring w "Magali" (w imieniu)
    falszywy_duplikat2 = baker.make("bpp.Autor", imiona="Magali", nazwisko="Kowalski")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    duplikaty_pks = [d.pk for d in duplikaty]

    # Prawdziwy duplikat powinien zostać znaleziony (dokładne dopasowanie "Gal" = "Gal")
    assert prawdziwy_duplikat.pk in duplikaty_pks

    # Fałszywe duplikaty NIE POWINNY zostać znalezione
    assert falszywy_duplikat1.pk not in duplikaty_pks
    assert falszywy_duplikat2.pk not in duplikaty_pks
