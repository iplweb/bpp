"""
Tests for PBNClient upload_publication method.

For sync tests, see test_client_sync.py
For discipline tests, see test_client_disciplines.py
For helper/GUI tests, see test_client_helpers.py
"""

import pytest
from model_bakery import baker

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_STATEMENTS,
)
from pbn_api.const import (
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import SameDataUploadedRecently, StatementsMissing
from pbn_api.models import Publication, SentData


class PBNTestClientException(Exception):
    pass


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_nie_trzeba(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    # Praca ma autora z dyscypliną → adapter generuje statements w JSON →
    # ścieżka /v1/publications (all-in-one, bez konwersji pól).
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": "test-123"
    }

    js = WydawnictwoPBNAdapter(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    ).pbn_get_json()
    SentData.objects.create_or_update_before_upload(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, js
    )

    baker.make(Publication, pk="test-123")

    SentData.objects.mark_as_successful(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uid_id="test-123"
    )

    with pytest.raises(SameDataUploadedRecently):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_exception(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
):
    # Praca z dyscypliną idzie do /v1/publications.
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = (
        PBNTestClientException("nei")
    )

    with pytest.raises(PBNTestClientException):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_z_statements_idzie_do_v1_publications(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication
):
    """Praca z lokalnymi statements → POST /v1/publications (all-in-one)."""
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }

    objectId, ret, js, bez_oswiadczen = pbn_client.upload_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert objectId == pbn_publication.pk
    assert bez_oswiadczen is False

    # Body wysłane do /v1/publications zawiera klucz "statements"
    # (surowy payload z adaptera, bez konwersji pól).
    sent_body = pbn_client.transport.input_values[PBN_POST_PUBLICATIONS_URL]["body"]
    assert isinstance(sent_body, dict)
    assert "statements" in sent_body
    # Pole "givenNames" zostaje (konwersja /v1/repositorium nie była wywołana).
    assert "givenNames" in sent_body["authors"][0]

    sent_data = SentData.objects.get_for_rec(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert sent_data.api_url is not None
    assert sent_data.api_url.endswith(PBN_POST_PUBLICATIONS_URL)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_bez_statements_idzie_do_repo(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication, uczelnia
):
    """Praca bez lokalnych statements + flaga uczelni → POST /v1/repositorium/publications."""
    uczelnia.pbn_wysylaj_bez_oswiadczen = True
    uczelnia.save()
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all().update(
        dyscyplina_naukowa=None
    )

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_publication.pk}
    ]

    objectId, ret, js, bez_oswiadczen = pbn_client.upload_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert objectId == pbn_publication.pk
    assert bez_oswiadczen is True

    # Body wysłane do /v1/repositorium/publications: lista, BEZ statements,
    # po konwersji pól (givenNames → firstName).
    sent_body = pbn_client.transport.input_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL][
        "body"
    ]
    assert isinstance(sent_body, list) and len(sent_body) == 1
    assert "statements" not in sent_body[0]
    assert "firstName" in sent_body[0]["authors"][0]
    assert "givenNames" not in sent_body[0]["authors"][0]

    sent_data = SentData.objects.get_for_rec(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert sent_data.api_url is not None
    assert sent_data.api_url.endswith(PBN_POST_PUBLICATION_NO_STATEMENTS_URL)


@pytest.mark.django_db
def test_PBNClient_test_upload_publication_bez_dyscypliny_bez_flagi_blad(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, uczelnia
):
    """Brak dyscyplin + flaga uczelni False → StatementsMissing z adaptera."""
    uczelnia.pbn_wysylaj_bez_oswiadczen = False
    uczelnia.save()
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all().update(
        dyscyplina_naukowa=None
    )

    with pytest.raises(StatementsMissing):
        pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


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


# ============================================================
# Pre-upload clear: kasowanie PBN statements PRZED POST do
# /v1/repositorium/publications gdy BPP intent jest pusty
# ============================================================


@pytest.mark.django_db
def test_pre_upload_clear_kasuje_pbn_statements_przed_post_repo(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    uczelnia,
):
    """Praca z pbn_uid_id + PBN ma statements + BPP nie ma → DELETE PRZED POST."""
    from fixtures.pbn_api import pbn_pageable_json

    uczelnia.pbn_wysylaj_bez_oswiadczen = True
    uczelnia.pbn_kasuj_dyscypliny_selektywnie = True
    uczelnia.save()

    # BPP: praca bez dyscyplin lokalnych
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all().update(
        dyscyplina_naukowa=None
    )

    # PBN: ma 1 oświadczenie do skasowania
    pbn_uid = str(pbn_publication.pk)
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={pbn_uid}&size=5120"
    ] = pbn_pageable_json(
        [
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ]
    )
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=pbn_uid)
    pbn_client.transport.return_values[url_delete] = []
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_publication.pk}
    ]

    pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # DELETE wykonany (selektywny, per autor) PRZED POST publikacji
    assert url_delete in pbn_client.transport.input_values
    body = pbn_client.transport.input_values[url_delete]["body"]
    assert body["statementsOfPersons"][0]["personId"] == pbn_autor.pbn_uid_id
    # POST do repo wykonany
    assert PBN_POST_PUBLICATION_NO_STATEMENTS_URL in pbn_client.transport.input_values


@pytest.mark.django_db
def test_pre_upload_clear_pomija_gdy_pbn_puste(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    uczelnia,
):
    """PBN puste → tylko GET, brak DELETE."""
    from fixtures.pbn_api import pbn_pageable_json

    uczelnia.pbn_wysylaj_bez_oswiadczen = True
    uczelnia.save()

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all().update(
        dyscyplina_naukowa=None
    )

    pbn_uid = str(pbn_publication.pk)
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={pbn_uid}&size=5120"
    ] = pbn_pageable_json([])
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_publication.pk}
    ]

    pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=pbn_uid)
    assert url_delete not in pbn_client.transport.input_values
    assert PBN_POST_PUBLICATION_NO_STATEMENTS_URL in pbn_client.transport.input_values


@pytest.mark.django_db
def test_pre_upload_clear_pomija_bez_pbn_uid(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, uczelnia
):
    """Bez pbn_uid_id → ani GET ani DELETE (PBN nie ma odpowiednika pracy)."""
    uczelnia.pbn_wysylaj_bez_oswiadczen = True
    uczelnia.save()

    # Praca bez pbn_uid + bez dyscyplin
    assert pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id is None
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.all().update(
        dyscyplina_naukowa=None
    )

    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": "new-uid-123"}
    ]

    pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # Brak GET statements (URL nie został wywołany)
    assert all(
        PBN_GET_INSTITUTION_STATEMENTS not in url
        for url in pbn_client.transport.input_values
    )


@pytest.mark.django_db
def test_pre_upload_clear_pomija_dla_v1_publications_z_statements(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication
):
    """Ścieżka /v1/publications (z statements w body) → brak pre-clear.

    Statements idą razem z payloadem, więc nie kasujemy ich upfront.
    Drift wykrywa post-upload sync.
    """
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk
    }

    pbn_client.upload_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # Brak GET (pre-clear nie odpalił się dla all-in-one path)
    assert all(
        PBN_GET_INSTITUTION_STATEMENTS not in url
        for url in pbn_client.transport.input_values
    )
    # POST do /v1/publications wykonany
    assert PBN_POST_PUBLICATIONS_URL in pbn_client.transport.input_values
