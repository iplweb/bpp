"""
Tests for szukaj_kopii and znajdz_pierwszego_autora_z_duplikatami functions.
"""

import pytest
from model_bakery import baker

from deduplikator_autorow.utils import (
    szukaj_kopii,
    znajdz_pierwszego_autora_z_duplikatami,
)
from pbn_api.models import OsobaZInstytucji, Scientist

# ============================================================================
# Basic szukaj_kopii tests
# ============================================================================


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
    """Test wyszukiwania duplikatów z inicjałami - sprawdza że duplikat z pełnym
    imieniem (Jan M.) jest znajdowany, gdy główny autor ma pełne imiona (Jan Marian).
    Nowy kod wymaga dopasowania prefix >= 4 znaki dla podobnych imion.
    """
    # Duplikaty z imionami pasującymi do głównego autora (Jan Marian)
    # Duplikat z "Jan M." - ma pełne imię "Jan" pasujące do głównego
    duplikat3 = autor_maker(imiona="Jan M.", nazwisko="Gal-Cisoń")
    # Duplikat z pełnymi imionami - idealny match
    duplikat4 = autor_maker(imiona="Jan", nazwisko="Gal-Cisoń")
    # Duplikat z "Maria" - pasuje do "Marian" (prefix "Mari" >= 4 znaki)
    duplikat5 = autor_maker(imiona="Maria", nazwisko="Gal-Cisoń")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    # Duplikaty z pełnym imieniem "Jan" powinny być znajdowane
    assert duplikat3 in duplikaty
    assert duplikat4 in duplikaty
    assert duplikat5 in duplikaty


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


def test_szukaj_kopii_case_insensitive(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Test że wyszukiwanie jest case-insensitive"""
    duplikat1 = autor_maker(imiona="jan", nazwisko="gal-cisoń")
    duplikat2 = autor_maker(imiona="JAN", nazwisko="GAL-CISOŃ")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat1 in duplikaty
    assert duplikat2 in duplikaty


# ============================================================================
# Name/surname swap detection tests for szukaj_kopii
# ============================================================================


def test_szukaj_kopii_name_surname_swap_basic(autor_maker, tytuly):
    """Test wykrywania podstawowej zamiany imienia z nazwiskiem.

    Swap detection wymaga imion >= 5 znaków, dlatego używamy dłuższych imion.
    Kod wykrywa swap gdy nazwisko duplikatu = imię głównego oraz
    imię duplikatu = nazwisko głównego.
    """
    # Główny autor: imię "Janusz", nazwisko "Kowalski" (oba >= 5 znaków)
    glowny_autor = autor_maker(imiona="Janusz", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikat z zamienionymi polami: imię "Kowalski", nazwisko "Janusz"
    duplikat = autor_maker(imiona="Kowalski", nazwisko="Janusz")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    # Swap detection znajduje duplikat
    assert duplikat in duplikaty


def test_szukaj_kopii_name_surname_swap_compound_surname(autor_maker, tytuly):
    """Test wykrywania zamiany dla nazwisk dwuczłonowych.

    Swap detection działa dla nazwisk >= 5 znaków.
    """
    # Główny autor: imię "Janusz", nazwisko "Kowalski-Nowak" (oba >= 5 znaków)
    glowny_autor = autor_maker(imiona="Janusz", nazwisko="Kowalski-Nowak")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikat z pełnym nazwiskiem jako imieniem - swap detection
    duplikat1 = autor_maker(imiona="Kowalski-Nowak", nazwisko="Janusz")
    # Duplikat z częścią nazwiska jako imieniem - NIE powinien być znaleziony
    # (bo "Kowalski" nie zawiera "Kowalski-Nowak" w całości)
    duplikat2 = autor_maker(imiona="Kowalski", nazwisko="Janusz")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    # Pełna zamiana jest wykrywana
    assert duplikat1 in duplikaty
    # Częściowa zamiana NIE jest wykrywana przez swap detection
    # (imię "Kowalski" nie zawiera nazwiska "Kowalski-Nowak")
    assert duplikat2 not in duplikaty


def test_szukaj_kopii_name_surname_swap_multiple_first_names(autor_maker, tytuly):
    """Test wykrywania zamiany gdy autor ma wiele imion.

    Swap detection wykrywa kandydatów gdzie:
    - nazwisko duplikatu = jedno z imion głównego (>= 5 znaków)
    - imię duplikatu zawiera nazwisko głównego
    """
    # Główny autor: imiona "Janusz Marian", nazwisko "Kowalski"
    glowny_autor = autor_maker(imiona="Janusz Marian", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikat 1: nazwisko="Janusz" (= imię głównego), imię="Kowalski" (= nazwisko głównego)
    # Swap detection: nazwisko_dup="Janusz" == imie_glownego="Janusz" (>= 5 zn.) ✓
    #                 imie_dup="Kowalski" zawiera nazwisko_glownego="Kowalski" ✓
    duplikat1 = autor_maker(imiona="Kowalski", nazwisko="Janusz")

    # Duplikat 2: nazwisko="Marian" (= drugie imię głównego), imię="Kowalski" (= nazwisko głównego)
    # Swap detection: nazwisko_dup="Marian" == imie_glownego="Marian" (>= 5 zn.) ✓
    #                 imie_dup="Kowalski" zawiera nazwisko_glownego="Kowalski" ✓
    duplikat2 = autor_maker(imiona="Kowalski", nazwisko="Marian")

    # Duplikat 3: ma "Janusz" w imionach co pasuje do głównego przez regularne dopasowanie
    duplikat3 = autor_maker(imiona="Janusz Kowalski", nazwisko="Marian")

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    # Wszystkie duplikaty są znajdowane - swap detection dla 1 i 2, regularne dla 3
    assert duplikat1 in duplikaty
    assert duplikat2 in duplikaty
    assert duplikat3 in duplikaty


# ============================================================================
# znajdz_pierwszego_autora_z_duplikatami tests
# ============================================================================


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
    """Test z wieloma autorami mającymi duplikaty - powinien zwrócić pierwszego.
    Duplikaty muszą używać pełnych imion zamiast inicjałów (nowy kod jest bardziej restrykcyjny).
    """
    # Utwórz pierwszego autora z duplikatem
    autor1 = autor_maker(imiona="Janusz", nazwisko="Kowalski")
    scientist1 = baker.make(Scientist, lastName="Kowalski", name="Janusz")
    autor1.pbn_uid = scientist1
    autor1.save()
    osoba1 = baker.make(OsobaZInstytucji, personId=scientist1)  # noqa
    # Duplikat z pełnym imieniem (nie inicjałem)
    duplikat1 = baker.make("bpp.Autor", imiona="Janusz", nazwisko="Kowalski")  # noqa

    # Utwórz drugiego autora z duplikatem
    autor2 = autor_maker(imiona="Anneta", nazwisko="Nowak")
    scientist2 = baker.make(Scientist, lastName="Nowak", name="Anneta")
    autor2.pbn_uid = scientist2
    autor2.save()
    osoba2 = baker.make(OsobaZInstytucji, personId=scientist2)  # noqa
    # Duplikat z pełnym imieniem (nie inicjałem)
    duplikat2 = baker.make("bpp.Autor", imiona="Anneta", nazwisko="Nowak")  # noqa

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


# ============================================================================
# OsobaZInstytucji exclusion tests
# ============================================================================


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
    """Test że autorzy bez własnego OsobaZInstytucji MOGĄ być wykrywani jako duplikaty.
    Nowy kod jest bardziej restrykcyjny - inicjały (np. "J.") nie są znajdowane.
    """
    # Główny autor: Janusz Kowalski
    glowny_autor = autor_maker(imiona="Janusz", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Duplikaty bez własnego OsobaZInstytucji (różne warianty imienia/nazwiska)
    # Używamy baker.make żeby utworzyć NOWE obiekty a nie get_or_create
    duplikat1 = baker.make(
        "bpp.Autor", imiona="Janusz", nazwisko="Kowalski"
    )  # Identyczny
    # duplikat2 z inicjałem "J." nie będzie znajdowany - pomijamy
    duplikat3 = baker.make(
        "bpp.Autor", imiona="Janusz Adam", nazwisko="Kowalski"
    )  # Dodatkowe imię

    # Żaden z tych duplikatów nie ma pbn_uid ani OsobaZInstytucji

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    duplikaty_pks = [d.pk for d in duplikaty]

    # Duplikaty z pełnymi imionami powinny być wykryte
    assert duplikat1.pk in duplikaty_pks
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


# ============================================================================
# Regex escaping tests - regression tests for InvalidRegularExpression bug
# ============================================================================


@pytest.mark.django_db
def test_szukaj_kopii_nazwisko_with_parentheses(autor_maker, tytuly):
    """Regression test: surnames with parentheses don't cause regex errors.

    Bug: Author names containing regex metacharacters like parentheses were
    inserted directly into iregex patterns without re.escape(), causing
    PostgreSQL InvalidRegularExpression: "parentheses () not balanced" errors.
    """
    # Author with parentheses in surname
    glowny_autor = autor_maker(imiona="Jan", nazwisko="Kowalski (Junior)")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    # Should not raise InvalidRegularExpression
    duplikaty = szukaj_kopii(osoba_z_instytucji)
    assert duplikaty is not None  # No crash = success


@pytest.mark.django_db
def test_szukaj_kopii_imiona_with_parentheses(autor_maker, tytuly):
    """Regression test: first names with parentheses don't cause regex errors."""
    glowny_autor = autor_maker(imiona="Jan (John)", nazwisko="Kowalski")
    scientist = baker.make(Scientist)
    glowny_autor.pbn_uid = scientist
    glowny_autor.save()
    osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

    duplikaty = szukaj_kopii(osoba_z_instytucji)
    assert duplikaty is not None


@pytest.mark.django_db
def test_szukaj_kopii_with_regex_metacharacters(autor_maker, tytuly):
    """Regression test: various regex metacharacters don't cause errors.

    Tests that szukaj_kopii handles author names containing characters that
    have special meaning in regular expressions without throwing PostgreSQL
    InvalidRegularExpression errors.
    """
    test_cases = [
        ("Jan", "O'Brien [Jr.]"),  # brackets
        ("Jan*", "Kowalski"),  # asterisk
        ("Jan+Maria", "Kowalski"),  # plus
        ("Jan?", "Kowalski"),  # question mark
        ("Jan", "Kowalski.Smith"),  # dot
        ("Jan", "Ko^wal$ki"),  # anchors
        ("Jan", "Kowal|ski"),  # alternation
    ]

    for imiona, nazwisko in test_cases:
        glowny_autor = autor_maker(imiona=imiona, nazwisko=nazwisko)
        scientist = baker.make(Scientist)
        glowny_autor.pbn_uid = scientist
        glowny_autor.save()
        osoba_z_instytucji = baker.make(OsobaZInstytucji, personId=scientist)

        # Should not raise InvalidRegularExpression
        duplikaty = szukaj_kopii(osoba_z_instytucji)
        assert duplikaty is not None, f"Failed for: {imiona} {nazwisko}"
