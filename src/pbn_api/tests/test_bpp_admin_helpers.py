import pytest
from model_bakery import baker

from fixtures import MOCK_MONGO_ID
from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import (
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import AccessDeniedException
from pbn_api.models import Publication, SentData
from pbn_api.tests.utils import middleware

from django.contrib.messages import get_messages

from bpp.admin.helpers.pbn_api.gui import sprobuj_wyslac_do_pbn_gui
from bpp.models import Charakter_Formalny, Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_charakter_zly(
    rf,
    pbn_wydawnictwo_zwarte,
):
    req = rf.get("/")

    pbn_wydawnictwo_zwarte.charakter_formalny = baker.make(
        Charakter_Formalny, rodzaj_pbn=None
    )

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte)

    msg = get_messages(req)

    assert "nie będzie eksportowany do PBN" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_uczelnia_brak_obiektu(
    rf, pbn_wydawnictwo_zwarte_z_charakterem
):
    req = rf.get("/")

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte_z_charakterem)

    msg = get_messages(req)

    assert 'w systemie brakuje obiektu "Uczelnia"' in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_uczelnia_integracja_wylaczona(
    rf, pbn_wydawnictwo_zwarte_z_charakterem, uczelnia
):
    req = rf.get("/")

    uczelnia.pbn_integracja = False
    uczelnia.pbn_aktualizuj_na_biezaco = False
    uczelnia.save()

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte_z_charakterem)

    msg = get_messages(req)
    assert len(msg) == 1


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_dane_juz_wyslane(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_uczelnia, pbn_client, rf
):
    SentData.objects.updated(
        pbn_wydawnictwo_zwarte_z_charakterem,
        WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_z_charakterem).pbn_get_json(),
    )

    req = rf.get("/")

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "Identyczne dane rekordu" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_access_denied(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbn_client.transport.return_values[
        PBN_POST_PUBLICATIONS_URL
    ] = AccessDeniedException(url="foo", content="testujemy")

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "Brak dostępu --" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_brak_prawidlowej_odpowiedzi(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "elem": "coz, jakby nie. "
    }

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "nie odpowiedział prawidłowym PBN UID" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_inny_exception(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = ZeroDivisionError

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "Nie można zsynchronizować" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_inny_blad(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = Exception("test")

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "Nie można zsynchronizować" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_sukces(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "zostały zaktualizowane" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_ostrzezenie_brak_dyscypliny_autora(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    for wza in pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all():
        wza.afiliuje = True
        wza.przypieta = True
        wza.save()

        jednostka = wza.jednostka
        jednostka.skupia_pracownikow = True
        jednostka.save()

        autor = wza.autor
        autor.pbn_uid = None
        autor.pbn_uid_id = None
        autor.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "nie zostanie oświadczona" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_przychodzi_istniejacy_pbn_uid_dla_nowego_rekordu(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina: Wydawnictwo_Ciagle,
    pbn_client,
    rf,
    pbn_uczelnia,
):
    """Ten test sprawdza, jak zachowa się system w przypadku wysyłki nowego rekordu, gdy przyjdzie PBN UID
    takiego rekordu, który już istnieje"""

    req = rf.get("/")

    # To jest istniejące w bazie wydawnictwo ciągłe z PBN UID = MOCK_MONGO_ID ("123")
    publikacja = baker.make(Publication, pk=MOCK_MONGO_ID)
    istniejace_wydawnictwo_ciagle = baker.make(  # noqa
        Wydawnictwo_Ciagle, pbn_uid=publikacja
    )

    # To jest NOWO WYSYŁANE wydawnictwo ciągłe, które nie ma PBN UID
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = None
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save(update_fields=["pbn_uid"])

    # To jest odpowiedź z PBNu gdzie zwrotnie przyjdzie objectId = MOCK_MONGO_ID
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": MOCK_MONGO_ID
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=MOCK_MONGO_ID)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={MOCK_MONGO_ID}&size=5120"
    ] = []

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert (
        "w odpowiedzi z serwera PBN numer UID rekordu JUŻ ISTNIEJĄCEGO"
        in list(msg)[0].message
    )


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_przychodzi_inny_pbn_uid_dla_starego_rekordu(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina: Wydawnictwo_Ciagle,
    pbn_client,
    rf,
    pbn_uczelnia,
):
    """Ten test sprawdza, jak zachowa się system w przypadku wysyłki nowego rekordu, gdy przyjdzie PBN UID
    takiego rekordu, który już istnieje"""

    req = rf.get("/")

    # To jest istniejące w bazie wydawnictwo ciągłe z PBN UID = MOCK_MONGO_ID ("123")
    publikacja = baker.make(Publication, pk=MOCK_MONGO_ID)

    # To jest wydawnictwo ciągłe, które ma PBN UID
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = publikacja
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save(update_fields=["pbn_uid"])

    # To jest odpowiedź z PBNu gdzie zwrotnie przyjdzie objectId = MOCK_MONGO_ID*2
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": MOCK_MONGO_ID * 2
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=MOCK_MONGO_ID * 2)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={MOCK_MONGO_ID}&size=5120"
    ] = []

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "Wg danych z PBN zmodyfikowano PBN UID tego rekordu " in list(msg)[0].message
