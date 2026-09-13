"""Testy pomocników ISBN dla wyszukiwarek (``bpp.util.isbn``)."""

import pytest

from bpp.util.isbn import kanoniczny_isbn, warianty_isbn, wyglada_jak_isbn


@pytest.mark.parametrize(
    "wpisany,oczekiwany",
    [
        ("978-83-7430-653-9", "9788374306539"),
        ("9788374306539", "9788374306539"),
        ("978 83 7430 653 9", "9788374306539"),
        ("  978.83.7430.653.9  ", "9788374306539"),
        ("83-7430-653-x", "837430653X"),
        ("", ""),
        (None, ""),
    ],
)
def test_kanoniczny_isbn_zdejmuje_separatory(wpisany, oczekiwany):
    assert kanoniczny_isbn(wpisany) == oczekiwany


@pytest.mark.parametrize(
    "wpisany",
    [
        "978-83-7430-653-9",
        "9788374306539",
        "83-7430-653-1",
        "837430653X",
    ],
)
def test_wyglada_jak_isbn_rozpoznaje_poprawne(wpisany):
    assert wyglada_jak_isbn(wpisany)


def test_wyglada_jak_isbn_nie_waliduje_sumy_kontrolnej():
    """ISBN z literowką ma byc nadal traktowany jak ISBN, nie jak tytuł.

    ``isbnlib.notisbn`` liczy cyfrę kontrolną i odrzuca taki numer — przez co
    wyszukiwarka szukała go jako tytułu i cicho nie znajdowała niczego.
    """
    assert wyglada_jak_isbn("978-83-01-12345-6")
    assert wyglada_jak_isbn("9788301123456")


@pytest.mark.parametrize(
    "wpisany",
    [
        "",
        None,
        "Interna Szczeklika 2021",
        "10.1234/abcd",
        "616e76ca2467f070ae3355dd",  # mongoId — 24 znaki hex
        "1234567890123",  # 13 cyfr, ale nie prefiks 978/979
        "12345678",  # za krótkie
    ],
)
def test_wyglada_jak_isbn_odrzuca_nie_isbn(wpisany):
    assert not wyglada_jak_isbn(wpisany)


def test_warianty_isbn_dodaje_odpowiednik_isbn10():
    """PBN nie konwertuje ISBN-10 na ISBN-13, więc musimy podać obie formy."""
    assert warianty_isbn("978-83-7430-700-0") == ["9788374307000", "8374307005"]


def test_warianty_isbn_dodaje_odpowiednik_isbn13():
    assert warianty_isbn("0306406152") == ["0306406152", "9780306406157"]


def test_warianty_isbn_bez_duplikatow_gdy_konwersja_niemozliwa():
    """Zła suma kontrolna — isbnlib nie przeliczy, zostaje sama forma kanoniczna."""
    assert warianty_isbn("978-83-01-12345-6") == ["9788301123456"]


def test_warianty_isbn_pusty_dla_smieci():
    assert warianty_isbn("") == []
    assert warianty_isbn(None) == []
