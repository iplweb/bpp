"""
Tests for PBNClient upload_publication method.

For sync tests, see test_client_sync.py
For discipline tests, see test_client_disciplines.py
For helper/GUI tests, see test_client_helpers.py
"""

import pytest
from model_bakery import baker

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import PBN_POST_PUBLICATIONS_URL
from pbn_api.const import PBN_POST_PUBLICATION_NO_STATEMENTS_URL
from pbn_api.exceptions import SameDataUploadedRecently
from pbn_api.models import Publication, SentData


class PBNTestClientException(Exception):
    pass


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_nie_trzeba(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {"objectId": None}

    # Create SentData with submitted_successfully=True to trigger SameDataUploadedRecently
    sent_data = SentData.objects.create_or_update_before_upload(  # noqa
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
        WydawnictwoPBNAdapter(
            pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
        ).pbn_get_json(),
    )

    baker.make(Publication, pk="test-123")

    # Mark as successful to simulate previous successful upload
    SentData.objects.mark_as_successful(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uid_id="test-123"
    )

    with pytest.raises(SameDataUploadedRecently):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_exception(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = (
        PBNTestClientException("nei")
    )

    with pytest.raises(PBNTestClientException):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_wszystko_ok(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication
):
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }

    objectId, ret, js, bez_oswiadczen = pbn_client.upload_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert objectId == pbn_publication.pk


@pytest.mark.django_db
def test_PBNClient_post_publication_no_statements(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, uczelnia
):
    from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA
    from pbn_api.client import PBN_GET_PUBLICATION_BY_ID_URL

    uczelnia.pbn_wysylaj_bez_oswiadczen = True
    uczelnia.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": 123}
    ]
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=123)] = (
        MOCK_RETURNED_MONGODB_DATA
    )

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all().update(
        dyscyplina_naukowa=None
    )
    ret = pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
    assert ret
