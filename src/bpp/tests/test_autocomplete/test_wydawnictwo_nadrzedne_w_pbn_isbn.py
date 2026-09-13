"""Rozpoznawanie i wyszukiwanie ISBN w autocomplete „Wydawnictwo nadrzędne w PBN".

Zachowanie serwera PBN sprawdzone empirycznie na ``/api/v1/search/publications``:

* ISBN dopasowywany jest **dosłownie, po formie kanonicznej** — zapytanie
  z myślnikami zwraca zero wyników nawet wtedy, gdy PBN przechowuje ISBN
  właśnie z myślnikami;
* PBN nie przelicza ISBN-10 na ISBN-13 ani odwrotnie;
* ``type="BOOK"`` odcina ``EDITED_BOOK``, czyli praktycznie wszystkie realne
  wydawnictwa nadrzędne (prace zbiorowe pod redakcją).
"""

from unittest.mock import Mock, call

import pytest
from model_bakery import baker

from bpp.views.autocomplete.wydawnictwo_nadrzedne_w_pbn import (
    Wydawnictwo_Nadrzedne_W_PBNAutocomplete as Widok,
)
from pbn_api.models import Publication

ISBN13_Z_MYSLNIKAMI = "978-83-7430-700-0"
ISBN13_BEZ_MYSLNIKOW = "9788374307000"
ISBN10 = "8374307005"

MONGO_ID = "616e76ca2467f070ae3355dd"


def _klient(*wyniki):
    client = Mock()
    client.search_publications.side_effect = list(wyniki) or [[]]
    return client


# --- qualify_query -------------------------------------------------------


def test_qualify_query_rozpoznaje_isbn_z_myslnikami():
    assert Widok().qualify_query(ISBN13_Z_MYSLNIKAMI) == Widok.ISBN


def test_qualify_query_rozpoznaje_isbn_bez_myslnikow():
    assert Widok().qualify_query(ISBN13_BEZ_MYSLNIKOW) == Widok.ISBN


def test_qualify_query_rozpoznaje_isbn_ze_zla_suma_kontrolna():
    """Regresja: ``isbnlib.notisbn`` odrzucał taki numer, przez co wyszukiwarka
    szukała go jako tytułu i cicho nie znajdowała niczego."""
    assert Widok().qualify_query("978-83-01-12345-6") == Widok.ISBN


def test_qualify_query_rozpoznaje_mongoid():
    assert Widok().qualify_query(MONGO_ID) == Widok.MONGO_ID


def test_qualify_query_rozpoznaje_doi():
    assert Widok().qualify_query("10.1234/abcd.2021") == Widok.DOI


def test_qualify_query_reszta_to_tytul():
    assert Widok().qualify_query("Interna Szczeklika 2021") == Widok.TITLE


# --- zapytania do serwera PBN -------------------------------------------


def test_isbn_leci_do_pbn_bez_filtra_type():
    """``type="BOOK"`` odcinałby EDITED_BOOK — czyli realne okładki."""
    client = _klient([], [])
    list(Widok()._get_pbn_search_results(client, Widok.ISBN, ISBN13_Z_MYSLNIKAMI))

    for wywolanie in client.search_publications.call_args_list:
        assert "type" not in wywolanie.kwargs


def test_isbn_leci_do_pbn_w_formie_kanonicznej_i_w_obu_dlugosciach():
    client = _klient([], [])
    list(Widok()._get_pbn_search_results(client, Widok.ISBN, ISBN13_Z_MYSLNIKAMI))

    assert client.search_publications.call_args_list == [
        call(isbn=ISBN13_BEZ_MYSLNIKOW),
        call(isbn=ISBN10),
    ]


def test_isbn_nie_pyta_o_drugi_wariant_gdy_pierwszy_wystarczyl():
    """Zapytania mają być leniwe — drugi wariant to dodatkowy round-trip."""
    client = _klient([{"mongoId": MONGO_ID}], [])
    wyniki = Widok()._get_pbn_search_results(client, Widok.ISBN, ISBN13_Z_MYSLNIKAMI)

    assert next(iter(wyniki)) == {"mongoId": MONGO_ID}
    assert client.search_publications.call_args_list == [
        call(isbn=ISBN13_BEZ_MYSLNIKOW)
    ]


def test_tytul_leci_do_pbn_dla_edited_book_i_book():
    client = _klient([], [])
    list(Widok()._get_pbn_search_results(client, Widok.TITLE, "Interna Szczeklika"))

    assert client.search_publications.call_args_list == [
        call(title="Interna Szczeklika", type="EDITED_BOOK"),
        call(title="Interna Szczeklika", type="BOOK"),
    ]


def test_doi_leci_do_pbn_bez_filtra_type():
    client = _klient([])
    list(
        Widok()._get_pbn_search_results(
            client, Widok.DOI, "https://doi.org/10.1234/abcd"
        )
    )

    assert client.search_publications.call_args_list == [call(doi="10.1234/abcd")]


# --- lokalny cache -------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("wpisany", [ISBN13_Z_MYSLNIKAMI, ISBN13_BEZ_MYSLNIKOW, ISBN10])
def test_lokalnie_isbn_znajduje_publikacje_w_kazdym_zapisie(wpisany):
    baker.make(Publication, mongoId=MONGO_ID, title="Tytuł", isbn=ISBN13_BEZ_MYSLNIKOW)

    widok = Widok()
    widok.q = wpisany
    assert [x.pk for x in widok.get_queryset()] == [MONGO_ID]


@pytest.mark.django_db
def test_lokalnie_isbn_znajduje_gdy_pole_ma_dopisek():
    """PBN bywa zaśmiecony — ``9788374307000 (druk)`` to realny zapis."""
    baker.make(
        Publication,
        mongoId=MONGO_ID,
        title="Tytuł",
        isbn=f"{ISBN13_BEZ_MYSLNIKOW} (druk)",
    )

    widok = Widok()
    widok.q = ISBN13_Z_MYSLNIKAMI
    assert [x.pk for x in widok.get_queryset()] == [MONGO_ID]


# --- etykieta opcji „pobierz z PBN" -------------------------------------


def test_create_option_pokazuje_to_co_wpisal_uzytkownik():
    """Pokazywanie formy skanonizowanej myliło — user nie poznawał swojego ISBN-u."""
    (opcja,) = Widok().get_create_option({}, ISBN13_Z_MYSLNIKAMI)

    assert ISBN13_Z_MYSLNIKAMI in opcja["text"]
    assert opcja["id"] == ISBN13_Z_MYSLNIKAMI
