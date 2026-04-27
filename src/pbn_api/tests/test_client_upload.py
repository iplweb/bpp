"""
Tests for PBNClient upload_publication method.

For sync tests, see test_client_sync.py
For discipline tests, see test_client_disciplines.py
For helper/GUI tests, see test_client_helpers.py
"""

import pytest
from model_bakery import baker

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.const import PBN_POST_PUBLICATION_NO_STATEMENTS_URL
from pbn_api.exceptions import SameDataUploadedRecently
from pbn_api.models import Publication, SentData


class PBNTestClientException(Exception):
    pass


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_nie_trzeba(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    # Po refaktoryzacji upload_publication zawsze używa endpointu repo.
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": None}
    ]

    # SentData musi być tworzony z JSON po konwersji (bez statements,
    # firstName etc.) bo nowy upload_publication robi ten sam convert
    # przed porównaniem w ``check_if_upload_needed``.
    js = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    ).pbn_get_json()
    js = pbn_client.convert_json_with_statements_to_no_statements(js)
    SentData.objects.create_or_update_before_upload(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, js
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
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = (
        PBNTestClientException("nei")
    )

    with pytest.raises(PBNTestClientException):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_wszystko_ok(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication
):
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_publication.pk}
    ]

    objectId, ret, js, bez_oswiadczen = pbn_client.upload_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert objectId == pbn_publication.pk
    # Po refaktoryzacji ``bez_oswiadczen`` zawsze True (endpoint repo)
    assert bez_oswiadczen is True

    # SentData powinien mieć zapisany pełny URL endpointu (domena + ścieżka)
    sent_data = SentData.objects.get_for_rec(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert sent_data.api_url is not None
    assert sent_data.api_url.endswith(PBN_POST_PUBLICATION_NO_STATEMENTS_URL)


@pytest.mark.django_db
def test_PBNClient_post_publication_no_statements(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, uczelnia, monkeypatch
):
    """Smoke test że sync_publication używa endpoint repo dla pracy bez dyscyplin.

    Uczelnia z ``pbn_wysylaj_bez_oswiadczen=True`` pozwala na wysyłkę prac
    bez oświadczeń (inaczej adapter rzuca StatementsMissing w pbn_get_json).
    """
    from fixtures.pbn_api import MOCK_RETURNED_MONGODB_DATA
    from pbn_api.client import PBN_GET_PUBLICATION_BY_ID_URL
    from pbn_api.const import (
        PBN_GET_INSTITUTION_PUBLICATIONS_V2,
        PBN_GET_INSTITUTION_STATEMENTS,
    )

    uczelnia.pbn_wysylaj_bez_oswiadczen = True
    uczelnia.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": 123}
    ]
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=123)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    from fixtures import MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA
    from fixtures.pbn_api import pbn_pageable_json

    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"
    ] = pbn_pageable_json([])

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all().update(
        dyscyplina_naukowa=None
    )
    ret = pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)
    assert ret
