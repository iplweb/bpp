"""
Tests for PBNClient sync_publication method.

For upload tests, see test_client_upload.py
For discipline tests, see test_client_disciplines.py
For helper/GUI tests, see test_client_helpers.py
"""

import pytest

from bpp.decorators import json
from fixtures import MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA
from pbn_api.client import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.const import PBN_GET_INSTITUTION_PUBLICATIONS_V2
from pbn_api.exceptions import HttpException, PKZeroExportDisabled
from pbn_api.models import Publication, SentData


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
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = [
        {
            "id": "eaec3254-2eb1-44d9-8c3c-e68fc2a48bd9",
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

    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA

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
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA

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
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = []
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA

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
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    pbn_client.transport.return_values[
        PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=pbn_publication.pk)
    ] = []
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = [
        {
            "id": "eaec3254-2eb1-44d9-8c3c-e68fc2a48bd9",
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
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2
        + f"?publicationId={pbn_publication.pk}&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    url = PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=pbn_publication.pk)
    err_json = {
        "code": 400,
        "message": "Bad Request",
        "description": "Validation failed.",
        "details": {
            "publicationId": "Nie można usunąć oświadczeń. Nie istnieją oświadczenia "
            "dla publikacji (id = {pbn_publication.pk}) i instytucji (id = XXX)."
        },
    }

    pbn_client.transport.return_values[url] = HttpException(
        400, url, json.dumps(err_json)
    )

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = [
        {
            "id": "eaec3254-2eb1-44d9-8c3c-e68fc2a48bd9",
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
def test_upload_and_sync_publication_without_existing_publication(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    """
    Regression test for foreign key violation issue.

    Tests that upload_publication() doesn't fail when the Publication record
    doesn't exist yet in the local database, and that sync_publication()
    properly updates SentData with the publication link after downloading it.
    """
    # Use the same objectId as in MOCK_RETURNED_MONGODB_DATA
    from fixtures.pbn_api import MOCK_MONGO_ID

    new_object_id = MOCK_MONGO_ID

    # Ensure Publication doesn't exist
    assert not Publication.objects.filter(pk=new_object_id).exists()

    # Mock API response for upload (called internally by sync_publication)
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": new_object_id
    }

    # Mock API response for download_publication
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=new_object_id)
    ] = MOCK_RETURNED_MONGODB_DATA

    # Mock for objectId 456 from MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    # Mock empty statements response
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={new_object_id}&size=5120"
    ] = []

    # Mock institution publications v2 response
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + f"?publicationId={new_object_id}&size=10"
    ] = MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA

    # Call sync_publication() - this internally calls upload_publication()
    # which should succeed without FK error, then download_publication()
    # which should create the Publication and update SentData
    publication = pbn_client.sync_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )

    # Verify Publication now exists in database
    assert Publication.objects.filter(pk=new_object_id).exists()

    # Verify SentData was created and updated with the publication link
    sent_data = SentData.objects.get_for_rec(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert sent_data.pbn_uid_id == new_object_id
    assert sent_data.pbn_uid == publication
    assert sent_data.submitted_successfully is True
