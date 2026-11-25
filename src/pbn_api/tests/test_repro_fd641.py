"""FD#641: krótszą listę autorów widać w PROFILU INSTYTUCJI, nie w rekordzie.

Rekord publikacji w PBN ma komplet autorów, a profil instytucji — czyli to,
co ogląda redaktor uczelni — potrafi pokazywać ich mniej. Porównanie
z rekordem publikacji (FD#509) takiej pracy nie zauważa; te testy pilnują
porównania z profilem instytucji przy wysyłce.
"""

import copy
import uuid

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
from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA, pbn_pageable_json
from pbn_api.models import Publication, PublikacjaInstytucji_V2
from pbn_api.porownanie_autorow import porownaj_autorow_z_profilem
from pbn_api.tests.utils import middleware


def _osoba(nazwisko, imie):
    return {"lastName": nazwisko, "givenNames": imie}


def _profil(publikacja, uczelnia, autorzy, **inne_role):
    """Wpis profilu instytucji w kształcie zwracanym przez PBN (API v2)."""
    dane = {
        "uuid": str(uuid.uuid4()),
        "objectId": publikacja.pk,
        "title": "Praca",
        "authors": [
            {"lastName": nazwisko, "firstName": imie, "statement": False}
            for nazwisko, imie in autorzy
        ],
    }
    dane.update(inne_role)
    return PublikacjaInstytucji_V2.objects.create(
        uuid=dane["uuid"], objectId=publikacja, json_data=dane, uczelnia=uczelnia
    )


# --------------------------------------------------------------------------
# Porównanie wysłanych autorów z profilem instytucji
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd641_profil_ma_jednego_z_trzech(uczelnia):
    profil = _profil(baker.make(Publication), uczelnia, [("Nowak", "Jan")])
    wyslane = {
        "authors": [
            _osoba("Nowak", "Jan"),
            _osoba("Kowalski", "Adam"),
            _osoba("Lis", "Ewa"),
        ]
    }

    wynik = porownaj_autorow_z_profilem(wyslane, profil)

    assert (wynik.wyslano, wynik.zapisano) == (3, 1)
    assert wynik.niepelne is True
    assert wynik.brakujacy == ["Kowalski Adam", "Lis Ewa"]
    tekst = wynik.komunikat()
    assert "w profilu instytucji w PBN jest 1 z 3 wysłanych autorów" in tekst
    assert "brakuje 2" in tekst
    assert "Kowalski Adam, Lis Ewa" in tekst


@pytest.mark.django_db
def test_fd641_komplet_w_profilu_bez_ostrzezenia(uczelnia):
    profil = _profil(
        baker.make(Publication), uczelnia, [("Nowak", "Jan"), ("Lis", "Ewa")]
    )

    wynik = porownaj_autorow_z_profilem(
        {"authors": [_osoba("Nowak", "Jan"), _osoba("Lis", "Ewa")]}, profil
    )

    assert wynik.niepelne is False


def test_fd641_brak_wpisu_w_profilu_nie_porownuje():
    assert porownaj_autorow_z_profilem({"authors": [_osoba("Nowak", "Jan")]}, None) is (
        None
    )


@pytest.mark.django_db
def test_fd641_wysylka_ostrzega_gdy_profil_ma_mniej_a_rekord_komplet(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_client,
    pbn_uczelnia,
    rf,
    autor_jan_kowalski,
):
    """Sedno zgłoszenia: rekord publikacji w PBN ma OBU autorów (porównanie
    z FD#509 milczy), a profil instytucji jednego. NIE przechodzi na starym
    kodzie — tam nie było żadnego ostrzeżenia."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = praca.autorzy_set.get()
    praca.dodaj_autora(autor_jan_kowalski, wa.jednostka)

    rekord_pbn = copy.deepcopy(MOCK_RETURNED_MONGODB_DATA)
    rekord_pbn["versions"] = [
        {
            "current": True,
            "object": {
                "authors": {
                    "a1": {"lastName": wa.autor.nazwisko, "name": wa.autor.imiona},
                    "a2": {
                        "lastName": autor_jan_kowalski.nazwisko,
                        "name": autor_jan_kowalski.imiona,
                    },
                }
            },
        }
    ]
    profil_pbn = {
        "uuid": str(uuid.uuid4()),
        "objectId": "123",
        "title": praca.tytul_oryginalny,
        "authors": [
            {
                "lastName": wa.autor.nazwisko,
                "firstName": wa.autor.imiona,
                "statement": True,
            }
        ],
    }
    rv = pbn_client.transport.return_values
    rv[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")] = rekord_pbn
    rv[PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"] = (
        pbn_pageable_json([profil_pbn])
    )
    rv[PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"] = (
        pbn_pageable_json([])
    )
    rv[PBN_POST_INSTITUTION_STATEMENTS_URL] = {"status": "ok"}

    req = rf.get("/")
    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, praca, pbn_client=pbn_client)
    komunikaty = [(m.level_tag, str(m.message)) for m in get_messages(req)]

    assert not any("PBN zapisał" in tresc for _, tresc in komunikaty), komunikaty
    ostrzezenia = [
        tresc
        for poziom, tresc in komunikaty
        if "warning" in poziom and "w profilu instytucji w PBN jest" in tresc
    ]
    assert len(ostrzezenia) == 1, komunikaty
    assert "jest 1 z 2 wysłanych autorów" in ostrzezenia[0]
    assert autor_jan_kowalski.nazwisko in ostrzezenia[0]
    assert any("zaktualizowane" in tresc for _, tresc in komunikaty)


# --------------------------------------------------------------------------
# Odporność: sprawdzenie nie może zepsuć wysyłki ani czytać starej kopii
# --------------------------------------------------------------------------


class _Wpis:
    def __init__(self, json_data):
        self.json_data = json_data


@pytest.mark.parametrize(
    "dane",
    [None, {}, [1], {"title": "bez kolekcji osób"}],
)
def test_fd641_wpis_bez_kolekcji_osob_to_brak_danych_a_nie_zero(dane):
    wyslane = {"authors": [_osoba("Nowak", "Jan"), _osoba("Lis", "Ewa")]}

    assert porownaj_autorow_z_profilem(wyslane, _Wpis(dane)) is None


def test_fd641_nietypowe_elementy_kolekcji_nie_wywracaja_porownania():
    wyslane = {"authors": [_osoba("Nowak", "Jan"), _osoba("Lis", "Ewa")]}
    dane = {"authors": [None, "5e7093d7878c28a0473b1ac0"], "editors": 42}

    wynik = porownaj_autorow_z_profilem(wyslane, _Wpis(dane))

    assert (wynik.wyslano, wynik.zapisano) == (2, 0)


def _odpowiedzi_pbn(pbn_client, rekord_pbn, profil_pbn):
    rv = pbn_client.transport.return_values
    rv[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")] = rekord_pbn
    rv[PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"] = (
        pbn_pageable_json(profil_pbn)
    )
    rv[PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"] = (
        pbn_pageable_json([])
    )
    rv[PBN_POST_INSTITUTION_STATEMENTS_URL] = {"status": "ok"}


def _wyslij(rf, praca, pbn_client):
    req = rf.get("/")
    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, praca, pbn_client=pbn_client)
    return [(m.level_tag, str(m.message)) for m in get_messages(req)]


@pytest.fixture
def praca_dwoch_autorow(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, autor_jan_kowalski
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = praca.autorzy_set.get()
    praca.dodaj_autora(autor_jan_kowalski, wa.jednostka)
    return praca, wa.autor


def _wpis_pbn(tytul, osoby, uid=None):
    return {
        "uuid": uid or str(uuid.uuid4()),
        "objectId": "123",
        "title": tytul,
        "authors": [
            {"lastName": o.nazwisko, "firstName": o.imiona, "statement": False}
            for o in osoby
        ],
    }


@pytest.mark.django_db
def test_fd641_porownanie_bierze_swiezy_wpis_a_nie_stara_kopie(
    praca_dwoch_autorow, pbn_client, pbn_uczelnia, rf, autor_jan_kowalski
):
    """W bazie leży STARSZY wpis profilu tej samej pracy (inne UUID, komplet
    autorów, niższy klucz). Liczy się to, co PBN zwrócił po tej wysyłce."""
    praca, pierwszy = praca_dwoch_autorow
    stara = baker.make(Publication, pk="123")
    PublikacjaInstytucji_V2.objects.create(
        uuid="00000000-0000-0000-0000-000000000001",
        objectId=stara,
        uczelnia=pbn_uczelnia,
        json_data=_wpis_pbn("stara", [pierwszy, autor_jan_kowalski]),
    )
    _odpowiedzi_pbn(
        pbn_client,
        MOCK_RETURNED_MONGODB_DATA,
        [_wpis_pbn("nowa", [pierwszy], uid="ffffffff-ffff-ffff-ffff-ffffffffffff")],
    )

    komunikaty = _wyslij(rf, praca, pbn_client)

    assert any(
        "w profilu instytucji w PBN jest 1 z 2" in tresc for _, tresc in komunikaty
    ), komunikaty


@pytest.mark.django_db
def test_fd641_pbn_nie_zwrocil_profilu_stara_kopia_nie_jest_porownywana(
    praca_dwoch_autorow, pbn_client, pbn_uczelnia, rf, monkeypatch
):
    """PBN nie oddał wpisu profilu po wysyłce: lokalna kopia „1 z 2” sprzed
    wysyłki nie może wywołać ostrzeżenia."""
    praca, pierwszy = praca_dwoch_autorow
    monkeypatch.setattr("pbn_api.client.publication_sync.time.sleep", lambda s: None)
    stara = baker.make(Publication, pk="123")
    PublikacjaInstytucji_V2.objects.create(
        uuid=uuid.uuid4(),
        objectId=stara,
        uczelnia=pbn_uczelnia,
        json_data=_wpis_pbn("stara", [pierwszy]),
    )
    _odpowiedzi_pbn(pbn_client, MOCK_RETURNED_MONGODB_DATA, [])

    komunikaty = _wyslij(rf, praca, pbn_client)

    assert not any("w profilu instytucji w PBN jest" in t for _, t in komunikaty)


@pytest.mark.django_db
def test_fd641_blad_porownania_nie_przerywa_wysylki(
    praca_dwoch_autorow, pbn_client, pbn_uczelnia, rf, monkeypatch, caplog
):
    """Praca już jest w PBN — awaria samego sprawdzenia nie może odebrać
    redaktorowi komunikatu o sukcesie ani pominąć dalszych kroków."""
    praca, pierwszy = praca_dwoch_autorow
    _odpowiedzi_pbn(
        pbn_client, MOCK_RETURNED_MONGODB_DATA, [_wpis_pbn("nowa", [pierwszy])]
    )

    def wybuch(*args, **kwargs):
        raise RuntimeError("awaria porównania")

    monkeypatch.setattr(
        "pbn_api.client.publication_sync.porownaj_autorow_z_profilem", wybuch
    )

    with caplog.at_level("ERROR", logger="pbn_api.client.publication_sync"):
        komunikaty = _wyslij(rf, praca, pbn_client)

    assert any(
        "success" in poziom and "zaktualizowane" in tresc
        for poziom, tresc in komunikaty
    ), komunikaty
    assert "awaria porównania" in caplog.text
