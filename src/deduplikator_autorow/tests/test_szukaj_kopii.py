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
