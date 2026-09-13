"""Wyszukiwarki globalne (publiczna i redakcyjna) znajdują rekordy po ISBN.

ISBN-y w BPP zapisywane są tak, jak wpisał je użytkownik — z myślnikami,
ze spacjami albo bez niczego. Obie wyszukiwarki muszą normalizować obie strony
porównania, przeszukiwać także ``e_isbn`` i radzić sobie z sytuacją, w której
rekord zapisano jako ISBN-13, a wpisano ISBN-10 (albo odwrotnie).
"""

import json

import pytest
from django.urls import reverse
from django.utils.http import urlencode

from bpp.models import Rekord

# ISBN-13 i jego odpowiednik ISBN-10 (poprawne sumy kontrolne).
ISBN13_Z_MYSLNIKAMI = "978-83-7430-700-0"
ISBN13_ZE_SPACJAMI = "978 83 7430 700 0"
ISBN13_BEZ_SEPARATOROW = "9788374307000"
ISBN10 = "8374307005"

# ISBN-10 z cyfrą kontrolną X — sprawdza zgodność wielkości liter po obu
# stronach porównania.
ISBN10_Z_X = "83-7430-653-X"
ISBN10_Z_X_BEZ_MYSLNIKOW = "837430653X"

TYTUL = "Zupełnie niepowtarzalny tytuł kontrolny"


def _url(nazwa, q):
    return reverse(nazwa) + "?" + urlencode({"q": q})


def _etykiety(res):
    """Etykiety wyników; obie wyszukiwarki grupują je po modelu."""
    etykiety = []
    for grupa in json.loads(res.content)["results"]:
        etykiety += [dziecko["text"] for dziecko in grupa.get("children", [])]
    return etykiety


@pytest.fixture
def zwarte_z_isbn(wydawnictwo_zwarte):
    def ustaw(isbn="", e_isbn=""):
        wydawnictwo_zwarte.tytul_oryginalny = TYTUL
        wydawnictwo_zwarte.isbn = isbn
        wydawnictwo_zwarte.e_isbn = e_isbn
        wydawnictwo_zwarte.save()
        Rekord.objects.full_refresh()
        return wydawnictwo_zwarte

    return ustaw


PRZYPADKI = [
    pytest.param(ISBN13_Z_MYSLNIKAMI, ISBN13_BEZ_SEPARATOROW, id="myslniki-w-bazie"),
    pytest.param(ISBN13_BEZ_SEPARATOROW, ISBN13_Z_MYSLNIKAMI, id="myslniki-we-wpisie"),
    pytest.param(ISBN13_ZE_SPACJAMI, ISBN13_BEZ_SEPARATOROW, id="spacje-w-bazie"),
    pytest.param(ISBN13_Z_MYSLNIKAMI, ISBN10, id="isbn10-szuka-isbn13"),
    pytest.param(ISBN10, ISBN13_BEZ_SEPARATOROW, id="isbn13-szuka-isbn10"),
    pytest.param(ISBN10_Z_X, ISBN10_Z_X_BEZ_MYSLNIKOW, id="cyfra-kontrolna-X"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("zapisany,wpisany", PRZYPADKI)
def test_publiczna_wyszukiwarka_znajduje_po_isbn(
    client, zwarte_z_isbn, zapisany, wpisany
):
    zwarte_z_isbn(isbn=zapisany)

    res = client.get(_url("bpp:navigation-autocomplete", wpisany))
    assert any(TYTUL in e for e in _etykiety(res))


@pytest.mark.django_db
@pytest.mark.parametrize("zapisany,wpisany", PRZYPADKI)
def test_redakcyjna_wyszukiwarka_znajduje_po_isbn(
    admin_client, zwarte_z_isbn, zapisany, wpisany
):
    zwarte_z_isbn(isbn=zapisany)

    res = admin_client.get(_url("bpp:admin-navigation-autocomplete", wpisany))
    assert any(TYTUL in e for e in _etykiety(res))


@pytest.mark.django_db
def test_publiczna_wyszukiwarka_znajduje_po_e_isbn(client, zwarte_z_isbn):
    zwarte_z_isbn(isbn="", e_isbn=ISBN13_Z_MYSLNIKAMI)

    res = client.get(_url("bpp:navigation-autocomplete", ISBN13_BEZ_SEPARATOROW))
    assert any(TYTUL in e for e in _etykiety(res))


@pytest.mark.django_db
def test_redakcyjna_wyszukiwarka_znajduje_po_e_isbn(admin_client, zwarte_z_isbn):
    zwarte_z_isbn(isbn="", e_isbn=ISBN13_Z_MYSLNIKAMI)

    res = admin_client.get(
        _url("bpp:admin-navigation-autocomplete", ISBN13_BEZ_SEPARATOROW)
    )
    assert any(TYTUL in e for e in _etykiety(res))


@pytest.mark.django_db
def test_wyszukiwanie_po_tytule_dziala_dalej(client, zwarte_z_isbn):
    """Kontrola: dołożenie ISBN-u nie może zepsuć wyszukiwania po tytule."""
    zwarte_z_isbn(isbn=ISBN13_Z_MYSLNIKAMI)

    res = client.get(_url("bpp:navigation-autocomplete", "niepowtarzalny"))
    assert any(TYTUL in e for e in _etykiety(res))
