import pytest
from model_bakery import baker

from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import (
    HttpException,
    PKZeroExportDisabled,
    SameDataUploadedRecently,
)
from pbn_api.models import Institution, Publication, SentData
from pbn_api.tests.utils import middleware

from django.contrib.messages import get_messages

from bpp.admin.helpers import sprobuj_wgrac_do_pbn
from bpp.decorators import json


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_nie_trzeba(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {"objectId": None}

    SentData.objects.updated(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
        ).pbn_get_json(),
    )

    with pytest.raises(SameDataUploadedRecently):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


class PBNTestClientException(Exception):
    pass


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_exception(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    pbn_client.transport.return_values[
        PBN_POST_PUBLICATIONS_URL
    ] = PBNTestClientException("nei")

    with pytest.raises(PBNTestClientException):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_wszystko_ok(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication
):

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }

    ret, js = pbn_client.upload_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert ret["objectId"] == pbn_publication.pk


@pytest.mark.django_db
def test_sync_publication_to_samo_id(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
):
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    stare_id = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = [
        {
            "id": "100",
            "addedTimestamp": "2020.05.06",
            "institutionId": pbn_jednostka.pbn_uid_id,
            "personId": pbn_autor.pbn_uid_id,
            "publicationId": pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id,
            "area": "200",
            "inOrcid": True,
            "type": "FOOBAR",
        }
    ]

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"
    assert stare_id == pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id


@pytest.mark.django_db
def test_sync_publication_tekstowo_podane_id(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication
):

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    pbn_client.sync_publication(
        f"wydawnictwo_zwarte:{pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}"
    )

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"


@pytest.mark.django_db
def test_sync_publication_nowe_id(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication
):
    assert pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id is None

    stare_id = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"
    assert stare_id != pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id


@pytest.mark.django_db
def test_sync_publication_wysylka_z_zerowym_pk(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_uczelnia,
):
    pbn_uczelnia.pbn_api_nie_wysylaj_prac_bez_pk = True
    pbn_uczelnia.save()

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.punkty_kbn = 0
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    # To pójdzie
    pbn_client.sync_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, export_pk_zero=True
    )

    # To nie pójdzie
    with pytest.raises(PKZeroExportDisabled):
        pbn_client.sync_publication(
            pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, export_pk_zero=False
        )


@pytest.mark.django_db
def test_helpers_wysylka_z_zerowym_pk(
    rf, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia, admin_user
):
    pbn_uczelnia.pbn_integracja = (
        pbn_uczelnia.pbn_aktualizuj_na_biezaco
    ) = pbn_uczelnia.pbn_api_nie_wysylaj_prac_bez_pk = True
    pbn_uczelnia.save()

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.punkty_kbn = 0
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    # I jeszcze test z poziomu admina czy parametr z pbn_uczelnia jest przekazywany
    with middleware(req):
        sprobuj_wgrac_do_pbn(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
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
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    with middleware(req):
        sprobuj_wgrac_do_pbn(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
        msg = list(get_messages(req))

    assert len(msg) == 1 and str(msg[0]).find("y zaktualizowane") > -1

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

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    req = rf.get("/")
    req._uczelnia = pbn_uczelnia
    req.user = admin_user

    with middleware(req):
        sprobuj_wgrac_do_pbn(req, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
        msg = list(get_messages(req))

    assert len(msg) == 1 and str(msg[0]).find("y zaktualizowane") > -1

    iv = pbn_client.transport.input_values["/api/v1/publications"]
    assert iv["body"]["authors"][0]["affiliations"][0] == pbn_jednostka.pbn_uid_id
    assert (
        iv["body"]["institutions"][pbn_jednostka.pbn_uid_id]["objectId"]
        == pbn_jednostka.pbn_uid_id
    )


@pytest.mark.django_db
def test_sync_publication_kasuj_oswiadczenia_przed_wszystko_dobrze(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
):
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    stare_id = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[
        PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=pbn_publication.pk)
    ] = []
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = [
        {
            "id": "100",
            "addedTimestamp": "2020.05.06",
            "institutionId": pbn_jednostka.pbn_uid_id,
            "personId": pbn_autor.pbn_uid_id,
            "publicationId": pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id,
            "area": "200",
            "inOrcid": True,
            "type": "FOOBAR",
        }
    ]

    pbn_client.sync_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
        delete_statements_before_upload=True,
    )

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"
    assert stare_id == pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id


@pytest.mark.django_db
def test_sync_publication_kasuj_oswiadczenia_przed_blad_400_nie_zaburzy(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
):
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    stare_id = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA

    url = PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=pbn_publication.pk)
    err_json = {
        "code": 400,
        "message": "Bad Request",
        "description": "Validation failed.",
        "details": {
            "publicationId": "Nie można usunąć oświadczeń. Nie istnieją oświadczenia dla publikacji "
            "(id = {pbn_publication.pk}) i instytucji (id = XXX)."
        },
    }

    pbn_client.transport.return_values[url] = HttpException(
        400, url, json.dumps(err_json)
    )

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = [
        {
            "id": "100",
            "addedTimestamp": "2020.05.06",
            "institutionId": pbn_jednostka.pbn_uid_id,
            "personId": pbn_autor.pbn_uid_id,
            "publicationId": pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id,
            "area": "200",
            "inOrcid": True,
            "type": "FOOBAR",
        }
    ]

    pbn_client.sync_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
        delete_statements_before_upload=True,
    )

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"
    assert stare_id == pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id
