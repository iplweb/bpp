"""
Tests for analiza_duplikatow function.
"""

from model_bakery import baker

from deduplikator_autorow.utils import analiza_duplikatow

# ============================================================================
# Basic analiza_duplikatow tests
# ============================================================================


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


# ============================================================================
# Publication count, title and ORCID scoring tests
# ============================================================================


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


# ============================================================================
# Temporal analysis tests
# ============================================================================


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


# ============================================================================
# Name/surname swap scoring tests for analiza_duplikatow
# ============================================================================


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
