import pytest
from model_mommy import mommy

from bpp.models import Wydzial, Jednostka, Autor, Tytul
from import_dyscyplin.core import (
    przeanalizuj_plik_xls,
    matchuj_wydzial,
    matchuj_jednostke,
    matchuj_autora,
    pesel_md5,
    znajdz_naglowek,
)
from import_dyscyplin.exceptions import (
    ImproperFileException,
    HeaderNotFoundException,
    BadNoOfSheetsException,
)
from import_dyscyplin.models import Import_Dyscyplin_Row


def test_przeanalizuj_plik_xls_zly_plik(conftest_py):
    with pytest.raises(ImproperFileException):
        przeanalizuj_plik_xls(conftest_py, parent=None)


def test_przeanalizuj_plik_xls_wiele_skoroszytow(test3_multiple_sheets_xlsx):
    with pytest.raises(BadNoOfSheetsException):
        przeanalizuj_plik_xls(test3_multiple_sheets_xlsx, parent=None)


def test_przeanalizuj_plik_xls_dobry(test1_xlsx, import_dyscyplin):
    import_dyscyplin.plik.save("test.xlsx", open(test1_xlsx, "rb"))
    import_dyscyplin.stworz_kolumny()

    przeanalizuj_plik_xls(test1_xlsx, parent=import_dyscyplin)
    assert Import_Dyscyplin_Row.objects.count() == 6


def test_znajdz_naglowek_dobry(test1_xlsx):
    row, no = znajdz_naglowek(test1_xlsx)
    assert no == 0


def test_znajdz_naglowek_zly(test2_bad_header_xlsx):
    with pytest.raises(HeaderNotFoundException):
        znajdz_naglowek(test2_bad_header_xlsx)


def test_znajdz_naglowek_default(default_xlsx):
    znajdz_naglowek(default_xlsx)


@pytest.mark.parametrize(
    "szukany_string",
    ["II Lekarski", "II Lekarski ", "ii lekarski", "   ii lekarski  ",],
)
def test_matchuj_wydzial(szukany_string, db):
    w1 = mommy.make(Wydzial, nazwa="I Lekarski")
    w2 = mommy.make(Wydzial, nazwa="II Lekarski")

    assert matchuj_wydzial(szukany_string) == w2


@pytest.mark.parametrize(
    "szukany_string",
    ["Jednostka Pierwsza", "  Jednostka Pierwsza  \t", "jednostka pierwsza"],
)
def test_matchuj_jednostke(szukany_string, uczelnia, wydzial, db):
    j1 = mommy.make(
        Jednostka, nazwa="Jednostka Pierwsza", wydzial=wydzial, uczelnia=uczelnia
    )
    j2 = mommy.make(
        Jednostka,
        nazwa="Jednostka Pierwsza i Jeszcze",
        wydzial=wydzial,
        uczelnia=uczelnia,
    )

    assert matchuj_jednostke(szukany_string) == j1


def test_matchuj_autora_pesel_md5(autor_jan_nowak):
    autor_jan_nowak.pesel_md5 = "foobar"
    autor_jan_nowak.save()

    a, info = matchuj_autora(imiona="", nazwisko="", jednostka=None, pesel_md5="foobar")

    assert a == autor_jan_nowak


def test_matchuj_autora_imiona_nazwisko(autor_jan_nowak):
    a, info = matchuj_autora("Jan", "Nowak", jednostka=None)
    assert a == autor_jan_nowak


@pytest.mark.django_db
def test_matchuj_autora_po_aktualnej_jednostce():
    j1 = mommy.make(Jednostka)
    j2 = mommy.make(Jednostka)

    a1 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.dodaj_jednostke(j1)

    a2 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2.dodaj_jednostke(j2)

    a, info = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=None)
    assert a == None

    a, info = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j1)
    assert a == a1

    a, info = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j2)
    assert a == a2


@pytest.mark.django_db
def test_matchuj_autora_po_jednostce():
    j1 = mommy.make(Jednostka)
    j2 = mommy.make(Jednostka)

    a1 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.dodaj_jednostke(j1)
    a1.aktualna_jednostka = None
    a1.save()

    a2 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2.dodaj_jednostke(j2)
    a2.aktualna_jednostka = None
    a2.save()

    a, info = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j1)
    assert a == a1

    a, info = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j2)
    assert a == a2


@pytest.mark.django_db
def test_matchuj_autora_po_tytule():
    t = Tytul.objects.create(nazwa="prof hab", skrot="lol.")

    j1 = mommy.make(Jednostka)

    a1 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.tytul = t
    a1.save()

    a2 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")

    a, info = matchuj_autora(imiona="Jan", nazwisko="Kowalski",)
    assert a == None

    a, info = matchuj_autora(imiona="Jan", nazwisko="Kowalski", tytul_str="lol.")
    assert a == a1


def test_pesel_md5():
    assert pesel_md5(1.0) == pesel_md5(1) == pesel_md5("1")


@pytest.mark.django_db
def test_matchuj_autora_tytul_bug(jednostka):
    matchuj_autora("Kowalski", "Jan", jednostka, tytul_str="Doktur")
    assert True
