from model_mommy import mommy

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import (
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import AccessDeniedException
from pbn_api.models import SentData
from pbn_api.tests.conftest import MOCK_RETURNED_MONGODB_DATA
from pbn_api.tests.utils import middleware

from django.contrib.messages import get_messages

from bpp.admin.helpers import sprobuj_wgrac_do_pbn
from bpp.models import Charakter_Formalny


def test_sprobuj_wgrac_do_pbn_charakter_zly(
    rf,
    pbn_wydawnictwo_zwarte,
):
    req = rf.get("/")

    pbn_wydawnictwo_zwarte.charakter_formalny = mommy.make(
        Charakter_Formalny, rodzaj_pbn=None
    )

    with middleware(req):
        sprobuj_wgrac_do_pbn(req, pbn_wydawnictwo_zwarte)

    msg = get_messages(req)

    assert "nie będzie eksportowany do PBN" in list(msg)[0].message


def test_sprobuj_wgrac_do_pbn_uczelnia_brak_obiektu(
    rf, pbn_wydawnictwo_zwarte_z_charakterem
):
    req = rf.get("/")

    with middleware(req):
        sprobuj_wgrac_do_pbn(req, pbn_wydawnictwo_zwarte_z_charakterem)

    msg = get_messages(req)

    assert 'w systemie brakuje obiektu "Uczelnia"' in list(msg)[0].message


def test_sprobuj_wgrac_do_pbn_uczelnia_integracja_wylaczona(
    rf, pbn_wydawnictwo_zwarte_z_charakterem, uczelnia
):
    req = rf.get("/")

    uczelnia.pbn_integracja = False
    uczelnia.pbn_aktualizuj_na_biezaco = False
    uczelnia.save()

    with middleware(req):
        sprobuj_wgrac_do_pbn(req, pbn_wydawnictwo_zwarte_z_charakterem)

    msg = get_messages(req)
    assert len(msg) == 0


def test_sprobuj_wgrac_do_pbn_dane_juz_wyslane(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_uczelnia, pbnclient, rf
):
    SentData.objects.updated(
        pbn_wydawnictwo_zwarte_z_charakterem,
        WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_z_charakterem).pbn_get_json(),
    )

    req = rf.get("/")

    with middleware(req):
        sprobuj_wgrac_do_pbn(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbnclient
        )

    msg = get_messages(req)
    assert "Identyczne dane rekordu" in list(msg)[0].message


def test_sprobuj_wgrac_do_pbn_access_denied(
    pbn_wydawnictwo_zwarte_z_charakterem, pbnclient, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbnclient.transport.return_values[
        PBN_POST_PUBLICATIONS_URL
    ] = AccessDeniedException(url="foo", content="testujemy")

    with middleware(req):
        sprobuj_wgrac_do_pbn(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbnclient
        )

    msg = get_messages(req)
    assert "Brak dostępu --" in list(msg)[0].message


def test_sprobuj_wgrac_do_pbn_inny_blad(
    pbn_wydawnictwo_zwarte_z_charakterem, pbnclient, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbnclient.transport.return_values[PBN_POST_PUBLICATIONS_URL] = Exception("test")

    with middleware(req):
        sprobuj_wgrac_do_pbn(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbnclient
        )

    msg = get_messages(req)
    assert "Nie można zsynchronizować" in list(msg)[0].message


def test_sprobuj_wgrac_do_pbn_sukces(
    pbn_wydawnictwo_zwarte_z_charakterem, pbnclient, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbnclient.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    pbnclient.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbnclient.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    with middleware(req):
        sprobuj_wgrac_do_pbn(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbnclient
        )

    msg = get_messages(req)
    assert "zostały zaktualizowane" in list(msg)[0].message
