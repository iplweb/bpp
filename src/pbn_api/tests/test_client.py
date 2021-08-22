import pytest

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import (
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import SameDataUploadedRecently
from pbn_api.models import SentData
from pbn_api.tests.conftest import MOCK_RETURNED_MONGODB_DATA


def test_PBNClient_test_upload_publication_nie_trzeba(
    pbnclient, pbn_wydawnictwo_zwarte
):
    pbnclient.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {"objectId": None}

    SentData.objects.updated(
        pbn_wydawnictwo_zwarte,
        WydawnictwoPBNAdapter(pbn_wydawnictwo_zwarte).pbn_get_json(),
    )

    with pytest.raises(SameDataUploadedRecently):
        pbnclient.upload_publication(pbn_wydawnictwo_zwarte)


class PBNTestClientException(Exception):
    pass


def test_PBNClient_test_upload_publication_exception(pbnclient, pbn_wydawnictwo_zwarte):
    pbnclient.transport.return_values[
        PBN_POST_PUBLICATIONS_URL
    ] = PBNTestClientException("nei")

    with pytest.raises(PBNTestClientException):
        pbnclient.upload_publication(pbn_wydawnictwo_zwarte)


def test_PBNClient_test_upload_publication_wszystko_ok(
    pbnclient, pbn_wydawnictwo_zwarte, pbn_publication
):

    pbnclient.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }

    assert (
        pbnclient.upload_publication(pbn_wydawnictwo_zwarte)["objectId"]
        == pbn_publication.pk
    )


def test_sync_publication_to_samo_id(
    pbnclient, pbn_wydawnictwo_zwarte, pbn_publication, pbn_autor, pbn_jednostka
):
    pbn_wydawnictwo_zwarte.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte.save()

    stare_id = pbn_wydawnictwo_zwarte.pbn_uid_id

    pbnclient.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbnclient.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbnclient.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = [
        {
            "id": "100",
            "addedTimestamp": "2020.05.06",
            "institutionId": pbn_jednostka.pbn_uid_id,
            "personId": pbn_autor.pbn_uid_id,
            "publicationId": pbn_wydawnictwo_zwarte.pbn_uid_id,
            "area": "200",
            "inOrcid": True,
            "type": "FOOBAR",
        }
    ]

    pbnclient.sync_publication(pbn_wydawnictwo_zwarte)

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"
    assert stare_id == pbn_wydawnictwo_zwarte.pbn_uid_id


def test_sync_publication_tekstowo_podane_id(
    pbnclient, pbn_wydawnictwo_zwarte, pbn_publication
):

    pbnclient.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbnclient.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbnclient.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    pbnclient.sync_publication(f"wydawnictwo_zwarte:{pbn_wydawnictwo_zwarte.pk}")

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"


def test_sync_publication_nowe_id(pbnclient, pbn_wydawnictwo_zwarte, pbn_publication):
    assert pbn_wydawnictwo_zwarte.pbn_uid_id is None

    stare_id = pbn_wydawnictwo_zwarte.pbn_uid_id

    pbnclient.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }
    pbnclient.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=pbn_publication.pk)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbnclient.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []

    pbnclient.sync_publication(pbn_wydawnictwo_zwarte)

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"
    assert stare_id != pbn_wydawnictwo_zwarte.pbn_uid_id
