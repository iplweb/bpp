"""FD#641: krótszą listę autorów widać w PROFILU INSTYTUCJI, nie w rekordzie.

Rekord publikacji w PBN ma komplet autorów, a profil instytucji — czyli to,
co ogląda redaktor uczelni — potrafi pokazywać ich mniej. Porównanie
z rekordem publikacji (FD#509) takiej pracy nie zauważa; te testy pilnują
porównania z profilem instytucji i zestawienia prac już istniejących.
"""

import copy
import uuid

import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse
from model_bakery import baker
from pbn_client.const import (
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)

from bpp.admin.helpers.pbn_api.gui import sprobuj_wyslac_do_pbn_gui
from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Uczelnia
from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA, pbn_pageable_json
from pbn_api.models import Publication, PublikacjaInstytucji_V2, SentData
from pbn_api.porownanie_autorow import (
    porownaj_autorow_z_profilem,
    prace_z_niepelna_lista_autorow_w_profilu,
)
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
    assert "niepełne listy autorów w PBN" in tekst


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
# Zestawienie prac już istniejących
# --------------------------------------------------------------------------


@pytest.fixture
def dwie_prace(
    wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_nowak, autor_jan_kowalski,
    jednostka, uczelnia,
):
    """Artykuł: 2 autorów w BPP, 1 w profilu (niepełny). Książka: 1 i 1."""
    niepelna = wydawnictwo_ciagle
    niepelna.pbn_uid = baker.make(Publication)
    niepelna.save()
    niepelna.dodaj_autora(autor_jan_nowak, jednostka)
    niepelna.dodaj_autora(autor_jan_kowalski, jednostka)
    _profil(niepelna.pbn_uid, uczelnia, [("Nowak", "Jan")])

    pelna = wydawnictwo_zwarte
    pelna.pbn_uid = baker.make(Publication)
    pelna.save()
    pelna.dodaj_autora(autor_jan_nowak, jednostka)
    _profil(pelna.pbn_uid, uczelnia, [("Nowak", "Jan")])
    return niepelna, pelna


@pytest.mark.django_db
def test_fd641_zestawienie_pokazuje_tylko_niepelne(dwie_prace, uczelnia):
    niepelna, _pelna = dwie_prace

    wynik = prace_z_niepelna_lista_autorow_w_profilu(uczelnia)

    assert [w.rekord.pk for w in wynik] == [niepelna.pk]
    wiersz = wynik[0]
    assert (wiersz.w_bpp, wiersz.w_profilu, wiersz.brakuje) == (2, 1, 1)
    assert wiersz.wyslana_z_bpp is False


@pytest.mark.django_db
def test_fd641_zestawienie_liczy_wszystkie_role_razem(dwie_prace, uczelnia):
    """Drugi autor zapisany w profilu jako redaktor nie jest „brakujący”."""
    niepelna, _pelna = dwie_prace
    wpis = PublikacjaInstytucji_V2.objects.get(objectId=niepelna.pbn_uid)
    wpis.json_data["editors"] = [{"lastName": "Kowalski", "firstName": "Jan"}]
    wpis.save()

    assert prace_z_niepelna_lista_autorow_w_profilu(uczelnia) == []


@pytest.mark.django_db
def test_fd641_zestawienie_tylko_wlasna_uczelnia(dwie_prace, uczelnia):
    inna = baker.make(Uczelnia)

    assert prace_z_niepelna_lista_autorow_w_profilu(inna) == []


@pytest.mark.django_db
def test_fd641_zestawienie_zaznacza_prace_wyslane_z_bpp(dwie_prace, uczelnia):
    niepelna, _pelna = dwie_prace
    SentData.objects.create(
        object=niepelna,
        data_sent={},
        uploaded_okay=True,
        pbn_uid=niepelna.pbn_uid,
        uczelnia=uczelnia,
    )

    assert prace_z_niepelna_lista_autorow_w_profilu(uczelnia)[0].wyslana_z_bpp is True


@pytest.mark.django_db
def test_fd641_strona_zestawienia(dwie_prace, uczelnia, admin_client):
    niepelna, pelna = dwie_prace

    tresc = admin_client.get(reverse("pbn_api:niepelne-listy-autorow")).content.decode()

    assert 'id="niepelne-listy-autorow"' in tresc
    assert reverse("admin:bpp_wydawnictwo_ciagle_change", args=(niepelna.pk,)) in tresc
    assert reverse("admin:bpp_wydawnictwo_zwarte_change", args=(pelna.pk,)) not in (
        tresc
    )


@pytest.mark.django_db
def test_fd641_strona_zestawienia_pusta(uczelnia, admin_client):
    tresc = admin_client.get(reverse("pbn_api:niepelne-listy-autorow")).content.decode()

    assert 'id="brak-prac"' in tresc


@pytest.mark.django_db
def test_fd641_strona_zestawienia_uprawnienia(uczelnia, client, django_user_model):
    url = reverse("pbn_api:niepelne-listy-autorow")
    assert client.get(url).status_code == 302  # niezalogowany → logowanie

    zwykly = django_user_model.objects.create_user("zwykly", password="x")
    client.force_login(zwykly)
    assert client.get(url).status_code == 403

    zwykly.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    assert client.get(url).status_code == 200
