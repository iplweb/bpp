"""
Tests for PBN helper/GUI functions.

For upload tests, see test_client_upload.py
For sync tests, see test_client_sync.py
For discipline tests, see test_client_disciplines.py
"""

import pytest
from django.contrib.messages import get_messages
from model_bakery import baker

from bpp.admin.helpers.pbn_api.gui import sprobuj_wyslac_do_pbn_gui
from fixtures.pbn_api import (
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
)
from pbn_api.models import Institution, Publication
from pbn_api.tests.utils import middleware


@pytest.mark.django_db
def test_helpers_wysylka_z_zerowym_pk(
    rf, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia, admin_user
):
    pbn_uczelnia.pbn_integracja = pbn_uczelnia.pbn_aktualizuj_na_biezaco = (
        pbn_uczelnia.pbn_api_nie_wysylaj_prac_bez_pk
    ) = True
    pbn_uczelnia.save()

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.punkty_kbn = 0
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    # I jeszcze test z poziomu admina czy parametr z pbn_uczelnia jest przekazywany
    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
        msg = list(get_messages(req))

    assert "wyłączony w konfiguracji" in msg[0].message


@pytest.mark.django_db
def test_helpers_wysylka_z_uid_uczelni(
    rf,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_autor_z_dyscyplina,
    pbn_uczelnia,
    admin_user,
    pbn_client,
    monkeypatch,
):
    odpowiednik = baker.make(Institution, mongoId="PBN_UID_UCZELNI----")

    baker.make(Publication, mongoId=pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk)

    pbn_uczelnia.pbn_uid = odpowiednik
    pbn_uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie = True
    pbn_uczelnia.save()

    pbn_uczelnia.pbn_integracja = pbn_uczelnia.pbn_aktualizuj_na_biezaco = True
    pbn_uczelnia.save()

    # Ten test bada UID uczelni w body, nie synchronizację statements —
    # wymuszamy pustą intencję żeby _sync_statements_with_pbn nie próbował
    # POST /v2/statements. Uczelnia musi mieć pbn_wysylaj_bez_oswiadczen
    # żeby adapter.pbn_get_json nie rzucił StatementsMissing.
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()
    monkeypatch.setattr(
        WydawnictwoPBNAdapter,
        "pbn_get_json_statements",
        lambda self, _lst=None: [],
    )

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}
    ]
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(
            id=pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk
        )
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2
        + f"?publicationId={pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}&size=5120"
    ] = pbn_pageable_json([])
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
        msg = list(get_messages(req))

    # Nowy flow może wyemitować dodatkowe info-messages o sync statements
    # (np. "Oświadczenia identyczne"); szukamy końcowego success-message.
    assert any("y zaktualizowane" in str(m) for m in msg)

    # Po refaktoryzacji: endpoint repo zwraca body jako lista [js]; autorzy
    # po ``convert_json_with_statements_to_no_statements`` używają pola
    # ``firstName`` zamiast ``givenNames`` (konwersja w adapterze).
    iv = pbn_client.transport.input_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL]
    body = iv["body"][0]
    assert body["authors"][0]["affiliations"][0] == odpowiednik.pk
    assert body["institutions"][odpowiednik.pk]["objectId"] == odpowiednik.pk


@pytest.mark.django_db
def test_helpers_wysylka_bez_uid_uczelni(
    rf,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_autor_z_dyscyplina,
    pbn_uczelnia,
    pbn_jednostka,
    admin_user,
    pbn_client,
    monkeypatch,
):
    odpowiednik = baker.make(Institution, mongoId="PBN_UID_UCZELNI----")

    baker.make(Publication, mongoId=pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk)

    pbn_uczelnia.pbn_uid = odpowiednik
    pbn_uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie = False
    pbn_uczelnia.save()

    pbn_uczelnia.pbn_integracja = pbn_uczelnia.pbn_aktualizuj_na_biezaco = True
    pbn_uczelnia.save()

    # Ten test bada afiliację jednostki w body, nie sync statements.
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()
    monkeypatch.setattr(
        WydawnictwoPBNAdapter,
        "pbn_get_json_statements",
        lambda self, _lst=None: [],
    )

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}
    ]
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(
            id=pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk
        )
    ] = MOCK_RETURNED_MONGODB_DATA

    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2
        + f"?publicationId={pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}&size=5120"
    ] = pbn_pageable_json([])
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
        msg = list(get_messages(req))

    assert any("y zaktualizowane" in str(m) for m in msg)

    iv = pbn_client.transport.input_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL]
    body = iv["body"][0]
    assert body["authors"][0]["affiliations"][0] == pbn_jednostka.pbn_uid_id
    assert (
        body["institutions"][pbn_jednostka.pbn_uid_id]["objectId"]
        == pbn_jednostka.pbn_uid_id
    )


def test_convert_json_with_statements_to_no_statements_removes_statements(
    pbn_client,
):
    js = {"authors": [], "statements": [{"type": "AUTHOR"}]}
    out = pbn_client.convert_json_with_statements_to_no_statements(js)
    assert "statements" not in out


def test_convert_json_with_statements_to_no_statements_no_statements_key(
    pbn_client,
):
    js = {"authors": []}
    pbn_client.convert_json_with_statements_to_no_statements(js)
