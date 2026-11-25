"""FD#509: po wysyłce porównujemy autorów WYSŁANYCH z ZAPISANYMI przez PBN.

Zgłoszenie brzmiało „w BPP 6 autorów, w PBN 4”. BPP wysyła wszystkich, więc
jedyne miejsce, w którym da się to zauważyć, to odpowiedź PBN zaraz po
wysyłce — redaktor ma dostać ostrzeżenie z liczbami, a nie sam sukces.
"""

import copy

import pytest
from django.contrib.messages import get_messages
from model_bakery import baker
from pbn_client.const import (
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)

from bpp.admin.helpers.pbn_api.gui import sprobuj_wyslac_do_pbn_gui
from fixtures.pbn_api import (
    MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA,
    MOCK_RETURNED_MONGODB_DATA,
    pbn_pageable_json,
)
from pbn_api.models import Publication
from pbn_api.porownanie_autorow import porownaj_autorow
from pbn_api.tests.utils import middleware


def _publikacja(object_dict):
    return baker.make(Publication, versions=[{"current": True, "object": object_dict}])


def _osoba(nazwisko, imie):
    return {"lastName": nazwisko, "givenNames": imie}


SZESCIORO = [
    _osoba("Nowak", "Jan"),
    _osoba("Kowalski", "Adam"),
    _osoba("Wiśniewska", "Anna"),
    _osoba("Lis", "Ewa"),
    _osoba("Mazur", "Piotr"),
    _osoba("Zając", "Olga"),
]


@pytest.mark.django_db
def test_fd509_pbn_zapisal_czterech_z_szesciu():
    """Kształt z produkcji: PBN oddaje autorów jako dict kluczowany UID-em."""
    pub = _publikacja(
        {
            "authors": {
                "a1": {"lastName": "Nowak", "name": "Jan"},
                "a2": {"lastName": "KOWALSKI", "name": "Adam"},
                "a3": {"lastName": "Wiśniewska", "name": "Anna"},
                "a4": {"lastName": "Lis", "name": "Ewa"},
            }
        }
    )

    wynik = porownaj_autorow({"authors": SZESCIORO}, pub)

    assert (wynik.wyslano, wynik.zapisano) == (6, 4)
    assert wynik.niepelne is True
    assert wynik.brakujacy == ["Mazur Piotr", "Zając Olga"]
    tekst = wynik.komunikat()
    assert "PBN zapisał 4 z 6 wysłanych autorów" in tekst
    assert "brakuje 2" in tekst
    assert "Mazur Piotr, Zając Olga" in tekst


@pytest.mark.django_db
def test_fd509_komplet_autorow_bez_ostrzezenia():
    pub = _publikacja({"authors": [dict(a) for a in SZESCIORO]})

    wynik = porownaj_autorow({"authors": SZESCIORO}, pub)

    assert (wynik.wyslano, wynik.zapisano) == (6, 6)
    assert wynik.niepelne is False
    assert wynik.brakujacy == []


@pytest.mark.django_db
def test_fd509_role_liczone_razem():
    """Osoba przeniesiona przez PBN z autorów do redaktorów nie „znika”."""
    pub = _publikacja(
        {
            "authors": [_osoba("Nowak", "Jan")],
            "editors": [_osoba("Kowalski", "Adam")],
        }
    )

    wynik = porownaj_autorow(
        {"authors": [_osoba("Nowak", "Jan"), _osoba("Kowalski", "Adam")]}, pub
    )

    assert wynik.niepelne is False


@pytest.mark.django_db
def test_fd509_dwoch_autorow_o_tym_samym_nazwisku():
    pub = _publikacja({"authors": [_osoba("Nowak", "Jan")]})

    wynik = porownaj_autorow(
        {"authors": [_osoba("Nowak", "Jan"), _osoba("Nowak", "Jan")]}, pub
    )

    assert (wynik.wyslano, wynik.zapisano) == (2, 1)
    assert wynik.brakujacy == ["Nowak Jan"]


@pytest.mark.django_db
def test_fd509_odpowiedz_pbn_bez_danych_publikacji_nie_porownuje():
    pub = baker.make(Publication, versions=[{"current": True}])

    assert porownaj_autorow({"authors": SZESCIORO}, pub) is None


@pytest.mark.django_db
def test_fd509_wysylka_z_formularza_ostrzega_gdy_pbn_zapisal_mniej_autorow(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_client,
    pbn_uczelnia,
    rf,
    autor_jan_kowalski,
):
    """Cała ścieżka: praca ma 2 autorów, PBN w odpowiedzi oddaje jednego."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = praca.autorzy_set.get()
    praca.dodaj_autora(autor_jan_kowalski, wa.jednostka)

    zapisane = copy.deepcopy(MOCK_RETURNED_MONGODB_DATA)
    zapisane["versions"] = [
        {
            "current": True,
            "object": {
                "authors": {
                    "5e709321878c28a0473a33f9": {
                        "lastName": wa.autor.nazwisko,
                        "name": wa.autor.imiona,
                    }
                }
            },
        }
    ]
    rv = pbn_client.transport.return_values
    rv[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")] = zapisane
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = zapisane
    rv[PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"] = (
        pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    )
    rv[PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"] = (
        pbn_pageable_json([])
    )
    rv[PBN_POST_INSTITUTION_STATEMENTS_URL] = {"status": "ok"}

    req = rf.get("/")
    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, praca, pbn_client=pbn_client)
    komunikaty = [(m.level_tag, str(m.message)) for m in get_messages(req)]

    wyslane = pbn_client.transport.input_values[PBN_POST_PUBLICATIONS_URL]["body"]
    assert len(wyslane["authors"]) == 2, "BPP wysyła wszystkich autorów"
    ostrzezenia = [
        tresc
        for poziom, tresc in komunikaty
        if "warning" in poziom and "PBN zapisał" in tresc
    ]
    assert len(ostrzezenia) == 1, komunikaty
    assert "PBN zapisał 1 z 2 wysłanych autorów" in ostrzezenia[0]
    assert autor_jan_kowalski.nazwisko in ostrzezenia[0]
    assert any("zaktualizowane" in tresc for _, tresc in komunikaty)
