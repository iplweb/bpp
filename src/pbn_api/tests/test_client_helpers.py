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
from fixtures import MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA
from pbn_api.client import (
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.const import PBN_GET_INSTITUTION_PUBLICATIONS_V2
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
):
    odpowiednik = baker.make(Institution, mongoId="PBN_UID_UCZELNI----")

    baker.make(Publication, mongoId=pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk)

    pbn_uczelnia.pbn_uid = odpowiednik
    pbn_uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie = True
    pbn_uczelnia.save()

    pbn_uczelnia.pbn_integracja = pbn_uczelnia.pbn_aktualizuj_na_biezaco = True
    pbn_uczelnia.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(
            id=pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk
        )
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2
        + f"?publicationId={pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
        msg = list(get_messages(req))

    assert len(msg) == 1
    # assert str(msg[0]).find("nie posiada oświadczeń") > -1
    assert str(msg[0]).find("y zaktualizowane") > -1

    iv = pbn_client.transport.input_values["/api/v1/publications"]
    assert iv["body"]["authors"][0]["affiliations"][0] == odpowiednik.pk
    assert iv["body"]["institutions"][odpowiednik.pk]["objectId"] == odpowiednik.pk


@pytest.mark.django_db
def test_helpers_wysylka_bez_uid_uczelni(
    rf,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_autor_z_dyscyplina,
    pbn_uczelnia,
    pbn_jednostka,
    admin_user,
    pbn_client,
):
    odpowiednik = baker.make(Institution, mongoId="PBN_UID_UCZELNI----")

    baker.make(Publication, mongoId=pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk)

    pbn_uczelnia.pbn_uid = odpowiednik
    pbn_uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie = False
    pbn_uczelnia.save()

    pbn_uczelnia.pbn_integracja = pbn_uczelnia.pbn_aktualizuj_na_biezaco = True
    pbn_uczelnia.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk
    }
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
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
        msg = list(get_messages(req))

    assert len(msg) == 1 and str(msg[0]).find("y zaktualizowane") > -1

    iv = pbn_client.transport.input_values["/api/v1/publications"]
    assert iv["body"]["authors"][0]["affiliations"][0] == pbn_jednostka.pbn_uid_id
    assert (
        iv["body"]["institutions"][pbn_jednostka.pbn_uid_id]["objectId"]
        == pbn_jednostka.pbn_uid_id
    )
