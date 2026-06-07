import pytest
from django.contrib.messages import get_messages
from model_bakery import baker

from bpp.admin.helpers.pbn_api.gui import sprobuj_wyslac_do_pbn_gui
from bpp.models import Charakter_Formalny, Wydawnictwo_Ciagle
from fixtures.pbn_api import (
    MOCK_MONGO_ID,
    MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA,
    MOCK_RETURNED_MONGODB_DATA,
    pbn_pageable_json,
)
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import (
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
)
from pbn_api.const import (
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import AccessDeniedException
from pbn_api.models import Publication, SentData
from pbn_api.tests.utils import middleware


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
    js = WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte_z_charakterem).pbn_get_json()
    js.pop("languageData", None)
    # Tagujemy SentData uczelnią clienta — od Track 4 lookup wysyłki zawęża
    # po uczelni (``self.uczelnia`` == ``pbn_uczelnia``).
    SentData.objects.updated(
        pbn_wydawnictwo_zwarte_z_charakterem,
        js,
        uploaded_okay=True,
        uczelnia=pbn_uczelnia,
    )

    req = rf.get("/")

    pub = baker.make(Publication, pk=MOCK_MONGO_ID)

    # Brak odpowiedzi URL zdefiniowanej dla /api/v1/repositorium/publications
    pbn_client.transport.return_values["/api/v1/repositorium/publications"] = [
        {"id": pub.pk}
    ]
    pbn_client.transport.return_values["/api/v1/publications/id/123"] = (
        MOCK_RETURNED_MONGODB_DATA
    )
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

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = (
        AccessDeniedException(url="foo", content="testujemy")
    )

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

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = {
        "elem": "coz, jakby nie. "
    }

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "zwrócił nieoczekiwaną odpowiedź" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_inny_exception(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = (
        ZeroDivisionError
    )

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

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = (
        Exception("test")
    )

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "Nie można zsynchronizować" in list(msg)[0].message


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_z_oswiadczeniami(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, rf, pbn_uczelnia
):
    req = rf.get("/")

    # Praca ma autora z dyscypliną → adapter generuje statements w JSON →
    # endpoint /v1/publications (all-in-one).
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="456")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = pbn_pageable_json([])
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    # Publikacja ma autorów z dyscyplinami → intencja BPP != puste PBN →
    # sync_statements wykona POST /v2/statements (i potrzebuje mocka).
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client=pbn_client
        )

    msg = list(get_messages(req))
    # Może być kilka wiadomości (info o sync oświadczeń + success końcowy).
    assert any("zostały zaktualizowane" in m.message for m in msg)


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_link_uzywa_uczelni_z_requestu(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    """Multi-hosted: link „Otwórz w PBN" w komunikacie sukcesu używa
    pbn_api_root uczelni Z REQUESTU, a nie zgaduje pierwszej-z-brzegu.

    Przy >1 uczelni ``link_do_pbn()`` bez argumentu degradowałby do None
    (get_single_uczelnia_or_none → None) → ``href="None"``. Po fixie link
    dostaje jawnie uczelnię z requestu.
    """
    from bpp.models import Uczelnia

    req = rf.get("/")
    # SiteResolutionMiddleware w produkcji ustawia request._uczelnia; tu
    # ustawiamy jawnie, żeby resolucja była deterministyczna mimo >1 uczelni.
    req._uczelnia = pbn_uczelnia

    pbn_uczelnia.pbn_api_root = "https://pbn-zrequestu.example.com"
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()

    # Druga uczelnia → get_single_uczelnia_or_none() zwróci None (>1).
    inne_site = baker.make("sites.Site", domain="inna-pbn.example.com")
    baker.make(
        Uczelnia,
        skrot="INNA",
        nazwa="Inna uczelnia",
        site=inne_site,
        pbn_api_root="https://pbn-inna.example.com",
    )

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": "123"}
    ]
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = pbn_pageable_json([])

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = list(get_messages(req))
    # Asercja CELOWO na URL publikacji (link_do_pbn), NIE na sam host — host
    # występuje też w link_do_pi (Profil Instytucji), które uczelnię już
    # dostaje. Pre-fix link_do_pbn() → None → ten fragment z hostem znika.
    oczekiwany = "pbn-zrequestu.example.com/core/#/publication/view/"
    assert any(oczekiwany in m.message for m in msg), [m.message for m in msg]


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_bez_oswiadczen_sukces(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia
):
    """Uczelnia z pbn_wysylaj_bez_oswiadczen=True pozwala na wysyłkę prac bez dyscyplin."""
    req = rf.get("/")

    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": "123"}
    ]
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = pbn_pageable_json([])

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = list(get_messages(req))
    # Po refaktoryzacji: sync_publication nie rozróżnia "bez oświadczeń" vs
    # "z oświadczeniami" (zawsze repo endpoint). Wiadomość o sukcesie
    # zawsze pojawia się po udanej wysyłce.
    assert any("zaktualizowane" in m.message for m in msg)


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

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": "123"}
    ]
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = pbn_pageable_json([])

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

    # Praca z dyscypliną → /v1/publications (all-in-one). Odpowiedź:
    # objectId = MOCK_MONGO_ID (już istnieje lokalnie pod inną pracą).
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": MOCK_MONGO_ID
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=MOCK_MONGO_ID)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={MOCK_MONGO_ID}&size=5120"
    ] = pbn_pageable_json([])
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)

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
@pytest.mark.serial
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
    publikacja2 = baker.make(Publication, pk="123123")  # noqa
    # To jest wydawnictwo ciągłe, które ma PBN UID
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = publikacja
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save(update_fields=["pbn_uid"])

    # Praca z dyscypliną → /v1/publications. Odpowiedź: objectId = MOCK_MONGO_ID*2.
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": MOCK_MONGO_ID * 2
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=MOCK_MONGO_ID * 2)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={MOCK_MONGO_ID}&size=5120"
    ] = pbn_pageable_json([])
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123123&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client=pbn_client
        )

    msg = get_messages(req)
    assert "Wg danych z PBN zmodyfikowano PBN UID tego rekordu " in list(msg)[0].message
