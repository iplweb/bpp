import pytest
from model_bakery import baker

from bpp.models import (
    Autor,
    Dyscyplina_Naukowa,
    Jednostka,
    Tytul,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
    Zrodlo,
)
from import_common.core import (
    _isbn_matches,
    _part_numbers_compatible,
    matchuj_dyscypline,
    matchuj_publikacje,
    matchuj_zrodlo,
)
from import_dyscyplin.core import matchuj_autora, matchuj_jednostke, matchuj_wydzial


@pytest.mark.parametrize(
    "szukany_string",
    [
        "II Lekarski",
        "II Lekarski ",
        "ii lekarski",
        "   ii lekarski  ",
    ],
)
def test_matchuj_wydzial(szukany_string, db):
    baker.make(Wydzial, nazwa="I Lekarski")
    w2 = baker.make(Wydzial, nazwa="II Lekarski")

    assert matchuj_wydzial(szukany_string) == w2


@pytest.mark.parametrize(
    "szukany_string",
    ["Jednostka Pierwsza", "  Jednostka Pierwsza  \t", "jednostka pierwsza"],
)
def test_matchuj_jednostke(szukany_string, uczelnia, wydzial, db):
    j1 = baker.make(
        Jednostka, nazwa="Jednostka Pierwsza", wydzial=wydzial, uczelnia=uczelnia
    )
    baker.make(
        Jednostka,
        nazwa="Jednostka Pierwsza i Jeszcze",
        wydzial=wydzial,
        uczelnia=uczelnia,
    )

    assert matchuj_jednostke(szukany_string) == j1


def test_matchuj_autora_imiona_nazwisko(autor_jan_nowak):
    a = matchuj_autora("Jan", "Nowak", jednostka=None)
    assert a == autor_jan_nowak


def test_matchuj_autora_imiona_nazwisko_dwa_imiona_w_matchu(autor_jan_nowak):
    a = matchuj_autora("Jan Tadeusz Wiśniowiecki", "Nowak", jednostka=None)
    assert a == autor_jan_nowak


@pytest.mark.django_db
def test_matchuj_autora_po_aktualnej_jednostce():
    j1 = baker.make(Jednostka)
    j2 = baker.make(Jednostka)

    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.dodaj_jednostke(j1)

    a2 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2.dodaj_jednostke(j2)

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=None)
    assert a is None

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j1)
    assert a == a1

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j2)
    assert a == a2


@pytest.mark.django_db
def test_matchuj_autora_po_jednostce():
    j1 = baker.make(Jednostka)
    j2 = baker.make(Jednostka)

    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.dodaj_jednostke(j1)
    a1.aktualna_jednostka = None
    a1.save()

    a2 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2.dodaj_jednostke(j2)
    a2.aktualna_jednostka = None
    a2.save()

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j1)
    assert a == a1

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j2)
    assert a == a2


@pytest.mark.django_db
def test_matchuj_autora_po_tytule():
    t = Tytul.objects.create(nazwa="prof hab", skrot="lol.")

    baker.make(Jednostka)

    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.tytul = t
    a1.save()

    baker.make(Autor, imiona="Jan", nazwisko="Kowalski")

    a = matchuj_autora(
        imiona="Jan",
        nazwisko="Kowalski",
    )
    # Jeżeli szukamy autora a jest podobny w systemie to matchuj tego ktory ma tytuł lub orcid
    assert a.pk == a1.pk

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", tytul_str="lol.")
    assert a.pk == a1.pk


@pytest.mark.django_db
def test_matchuj_autora_tytul_bug(jednostka):
    matchuj_autora("Kowalski", "Jan", jednostka, tytul_str="Doktur")
    assert True


@pytest.mark.parametrize(
    "kod,nazwa",
    [
        ("403_0", "aoijsdf"),
        ("403_0", None),
        (None, "foo"),
        ("403_0", "aoijsdf     "),
        ("403", "aoijsdf"),
        ("4.3", "aoijsdf"),
        ("nieno", "foo"),
        ("xxx", "foo (dziedzina nauk bylejakich)"),
    ],
)
@pytest.mark.django_db
def test_matchuj_dyscypline(kod, nazwa):
    d = Dyscyplina_Naukowa.objects.create(nazwa="foo", kod="4.3")

    assert matchuj_dyscypline(kod, nazwa) == d


@pytest.mark.django_db
def test_matchuj_dyscypline_o_Ziemi():
    NAZWA = "nauki o Ziemi i środowisku"
    d = Dyscyplina_Naukowa.objects.create(kod="123", nazwa=NAZWA)
    assert matchuj_dyscypline(kod=None, nazwa=NAZWA).pk == d.pk


@pytest.mark.django_db
def test_matchuj_zrodlo_by_mnisw_id():
    """Test matching Zrodlo by mniswId through PBN Journal"""
    from pbn_api.models import Journal

    # Create test data - Journal is a special model that needs versions data
    pbn_journal = Journal.objects.create(
        mongoId="test_journal_12345",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test Journal PBN",
                    "mniswId": 12345,
                    "issn": None,
                    "eissn": None,
                },
            }
        ],
    )
    # Manually set the mniswId field (normally done in save)
    pbn_journal.mniswId = 12345
    pbn_journal.title = "Test Journal PBN"
    pbn_journal.save()

    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal)

    # Should find by mniswId when no ISSN provided
    result = matchuj_zrodlo("Wrong Name", mnisw_id=12345)
    assert result == zrodlo

    # Should also work with string mniswId
    result = matchuj_zrodlo("Wrong Name", mnisw_id="12345")
    assert result == zrodlo

    # Should return None when mniswId doesn't exist
    result = matchuj_zrodlo("Some Name", mnisw_id=99999)
    assert result is None

    # Should return None when mniswId is invalid
    result = matchuj_zrodlo("Some Name", mnisw_id="invalid")
    assert result is None


@pytest.mark.django_db
def test_matchuj_zrodlo_issn_priority_over_mnisw_id():
    """Test that ISSN/E-ISSN matching takes priority over mniswId"""
    from pbn_api.models import Journal

    # Create two different journals
    pbn_journal1 = Journal.objects.create(
        mongoId="test_journal_11111",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Journal One", "mniswId": 11111},
            }
        ],
        mniswId=11111,
        title="Journal One",
    )

    zrodlo1 = baker.make(
        Zrodlo, nazwa="Journal One", pbn_uid=pbn_journal1, issn="1111-1111"
    )

    pbn_journal2 = Journal.objects.create(
        mongoId="test_journal_22222",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Journal Two", "mniswId": 22222},
            }
        ],
        mniswId=22222,
        title="Journal Two",
    )
    baker.make(
        Zrodlo, nazwa="Journal Two", pbn_uid=pbn_journal2
    )  # Create but not used in assertion

    # ISSN should take priority over mniswId
    result = matchuj_zrodlo("Some Name", issn="1111-1111", mnisw_id=22222)
    assert result == zrodlo1

    # E-ISSN should also take priority over mniswId
    zrodlo3 = baker.make(Zrodlo, nazwa="Journal Three", e_issn="3333-3333")
    result = matchuj_zrodlo("Some Name", e_issn="3333-3333", mnisw_id=22222)
    assert result == zrodlo3


@pytest.mark.django_db
def test_matchuj_zrodlo_mnisw_id_no_corresponding_zrodlo():
    """Test when PBN Journal exists but has no corresponding Zrodlo"""
    from pbn_api.models import Journal

    # Create PBN Journal without corresponding Zrodlo
    Journal.objects.create(
        mongoId="test_journal_33333",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Orphan Journal", "mniswId": 33333},
            }
        ],
        mniswId=33333,
        title="Orphan Journal",
    )

    # Should return None when no Zrodlo is linked
    result = matchuj_zrodlo("Orphan Journal", mnisw_id=33333)
    assert result is None


@pytest.mark.django_db
def test_matchuj_zrodlo_multiple_journals_same_mnisw_id():
    """Test handling multiple PBN Journals with same mniswId"""
    from pbn_api.models import Journal

    # Create multiple PBN Journals with same mniswId
    Journal.objects.create(  # First journal without Zrodlo
        mongoId="test_journal_44444_1",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Duplicate 1", "mniswId": 44444},
            }
        ],
        mniswId=44444,
        title="Duplicate 1",
    )
    pbn_journal2 = Journal.objects.create(
        mongoId="test_journal_44444_2",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Duplicate 2", "mniswId": 44444},
            }
        ],
        mniswId=44444,
        title="Duplicate 2",
    )

    # Only second journal has a Zrodlo
    zrodlo = baker.make(Zrodlo, nazwa="The Real Journal", pbn_uid=pbn_journal2)

    # Should find the Zrodlo linked to one of the journals
    result = matchuj_zrodlo("Some Name", mnisw_id=44444)
    assert result == zrodlo


# ===== Testy dla _part_numbers_compatible =====


@pytest.mark.parametrize(
    "title1,title2,expected",
    [
        # Oba bez numeru części - OK
        ("Tytuł publikacji", "Tytuł publikacji", True),
        ("Inny tytuł", "Jeszcze inny tytuł", True),
        # Oba z tym samym numerem części - OK
        ("Tytuł cz. II", "Tytuł część II", True),
        ("Tytuł cz. 2", "Tytuł cz. II", True),
        ("Tytuł tom III", "Tytuł cz. III", True),
        # Różne numery części - NIE OK
        ("Tytuł cz. II", "Tytuł cz. III", False),
        ("Tytuł cz. 2", "Tytuł cz. 3", False),
        ("Tytuł część I", "Tytuł część II", False),
        ("Tytuł tom I", "Tytuł tom IV", False),
        # Jeden ma numer części, drugi nie - NIE OK
        ("Tytuł cz. II", "Tytuł", False),
        ("Tytuł", "Tytuł cz. III", False),
        # None values - zakładamy kompatybilność
        (None, "Tytuł cz. II", True),
        ("Tytuł cz. II", None, True),
        (None, None, True),
    ],
)
def test_part_numbers_compatible(title1, title2, expected):
    assert _part_numbers_compatible(title1, title2) == expected


# ===== Testy dla matchuj_publikacje z numerami części =====


@pytest.mark.django_db
def test_matchuj_publikacje_rozroznia_numery_czesci(zrodlo):
    """Publikacje cz. II i cz. III nie powinny być matchowane."""
    # Utwórz publikację z cz. III
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=(
            "Znaczenie jakości wody w wielkostadnej produkcji drobiarskiej cz. III"
        ),
        rok=2020,
        zrodlo=zrodlo,
    )

    # cz. II NIE powinno matchować do cz. III
    result = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Znaczenie jakości wody w wielkostadnej produkcji drobiarskiej cz. II",
        year=2020,
    )
    assert result is None

    # cz. III powinno matchować
    result = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Znaczenie jakości wody w wielkostadnej produkcji drobiarskiej cz. III",
        year=2020,
    )
    assert result == pub


@pytest.mark.django_db
def test_matchuj_publikacje_ten_sam_numer_czesci(zrodlo):
    """Publikacje z tym samym numerem części powinny być matchowane."""
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Badania eksperymentalne cz. II",
        rok=2021,
        zrodlo=zrodlo,
    )

    # cz. II powinno matchować do cz. II (ten sam format)
    result = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Badania eksperymentalne cz. II",
        year=2021,
    )
    assert result == pub


@pytest.mark.django_db
def test_matchuj_publikacje_bez_numeru_czesci(zrodlo):
    """Publikacje bez numeru części powinny matchować normalnie."""
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Zwykła publikacja bez numeru części",
        rok=2022,
        zrodlo=zrodlo,
    )

    result = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Zwykła publikacja bez numeru części",
        year=2022,
    )
    assert result == pub


@pytest.mark.django_db
def test_matchuj_publikacje_rozroznia_tom_i_tom_ii(zrodlo):
    """Tom I i Tom II to różne publikacje."""
    baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Podręcznik akademicki tom I",
        rok=2020,
        zrodlo=zrodlo,
    )

    # tom II NIE powinno matchować do tom I
    result = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Podręcznik akademicki tom II",
        year=2020,
    )
    assert result is None


# ===== Testy dla _isbn_matches =====


class MockCandidate:
    """Klasa pomocnicza do testowania _isbn_matches."""

    def __init__(self, isbn=None, e_isbn=None):
        self.isbn = isbn
        self.e_isbn = e_isbn


@pytest.mark.parametrize(
    "candidate_isbn,candidate_e_isbn,search_isbn,expected",
    [
        # Brak ISBN do porównania - zawsze True
        (None, None, None, True),
        ("978-83-7430-668-3", None, None, True),
        # Kandydat bez ISBN - akceptujemy
        (None, None, "978-83-7430-668-3", True),
        ("", "", "978-83-7430-668-3", True),
        # ISBN się zgadza
        ("978-83-7430-668-3", None, "978-83-7430-668-3", True),
        ("9788374306683", None, "978-83-7430-668-3", True),  # normalizacja
        (None, "978-83-7430-668-3", "978-83-7430-668-3", True),  # e_isbn
        # ISBN się NIE zgadza
        ("978-83-7430-668-3", None, "9788374306706", False),
        ("9788374306683", None, "9788374306706", False),
        # Różne edycje tej samej książki - powinny NIE matchować
        ("978-83-7430-668-3", None, "978-83-7430-670-6", False),
    ],
)
def test_isbn_matches(candidate_isbn, candidate_e_isbn, search_isbn, expected):
    """Test funkcji _isbn_matches sprawdzającej zgodność ISBN."""
    candidate = MockCandidate(isbn=candidate_isbn, e_isbn=candidate_e_isbn)
    assert _isbn_matches(candidate, search_isbn) == expected


# ===== Testy dla matchuj_publikacje z różnymi ISBN =====


@pytest.mark.django_db
def test_matchuj_publikacje_rozroznia_rozdzialy_z_roznych_ksiazek():
    """Rozdziały o tym samym tytule z różnych książek NIE powinny się matchować.

    Przypadek: "Zaburzenia hemostazy w chorobach wątroby" z 2022 roku
    występuje zarówno w "Interna Szczeklika 2022" (ISBN 978-83-7430-668-3)
    jak i w "Interna Szczeklika 2022/23" (ISBN 9788374306706).
    To są RÓŻNE publikacje!
    """
    # Utwórz rozdział z pierwszej książki (mały podręcznik)
    baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Zaburzenia hemostazy w chorobach wątroby",
        rok=2022,
        isbn="9788374306706",  # mały podręcznik
    )

    # Szukamy rozdziału z dużej edycji - NIE powinno matchować
    result = matchuj_publikacje(
        Wydawnictwo_Zwarte,
        title="Zaburzenia hemostazy w chorobach wątroby",
        year=2022,
        isbn="978-83-7430-668-3",  # duża edycja - inny ISBN!
    )
    assert result is None


@pytest.mark.django_db
def test_matchuj_publikacje_matchuje_rozdzialy_z_tej_samej_ksiazki():
    """Rozdziały o tym samym tytule z tej samej książki POWINNY się matchować."""
    pub = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Zaburzenia hemostazy w chorobach wątroby",
        rok=2022,
        isbn="978-83-7430-668-3",
    )

    # Ten sam ISBN - powinno matchować
    result = matchuj_publikacje(
        Wydawnictwo_Zwarte,
        title="Zaburzenia hemostazy w chorobach wątroby",
        year=2022,
        isbn="978-83-7430-668-3",
    )
    assert result == pub


@pytest.mark.django_db
def test_matchuj_publikacje_bez_isbn_matchuje_normalnie():
    """Gdy nie podano ISBN, matchowanie po tytule działa normalnie."""
    pub = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Zaburzenia hemostazy w chorobach wątroby",
        rok=2022,
        isbn="978-83-7430-668-3",
    )

    # Brak ISBN w zapytaniu - powinno matchować (zachowanie wsteczne)
    result = matchuj_publikacje(
        Wydawnictwo_Zwarte,
        title="Zaburzenia hemostazy w chorobach wątroby",
        year=2022,
    )
    assert result == pub


@pytest.mark.django_db
def test_matchuj_publikacje_kandidat_bez_isbn_matchuje():
    """Gdy kandydat nie ma ISBN, matchowanie po tytule akceptuje go."""
    pub = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Zaburzenia hemostazy w chorobach wątroby",
        rok=2022,
        isbn="",  # brak ISBN w bazie (pusty string zamiast None)
        e_isbn="",
    )

    # Nawet z ISBN w zapytaniu - powinno matchować (kandydat bez ISBN)
    result = matchuj_publikacje(
        Wydawnictwo_Zwarte,
        title="Zaburzenia hemostazy w chorobach wątroby",
        year=2022,
        isbn="978-83-7430-668-3",
    )
    assert result == pub
