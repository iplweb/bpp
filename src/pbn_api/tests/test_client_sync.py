"""
Tests for PBNClient sync_publication method.

Logika wyboru endpointu w ``upload_publication``:
- praca z lokalnymi statements → ``POST /v1/publications`` (all-in-one,
  surowy payload), odpowiedź ``{"objectId": ...}``;
- praca bez lokalnych statements (uczelnia z
  ``pbn_wysylaj_bez_oswiadczen=True``) → ``POST /v1/repositorium/publications``
  (po konwersji), odpowiedź ``[{"id": ...}]``.

``sync_publication`` synchronizuje oświadczenia osobno przez
``_sync_statements_with_pbn`` — GET aktualnego stanu w PBN, diff z
intencją BPP (``pbn_get_json_statements``), selektywne DELETE (lub
batch — sterowane ``Uczelnia.pbn_kasuj_dyscypliny_selektywnie``) +
POST przez ``/api/v2/institution-profile/statements``. Działa
niezależnie od endpointu wysyłki publikacji.

For upload tests, see test_client_upload.py
For discipline tests, see test_client_disciplines.py
For helper/GUI tests, see test_client_helpers.py
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from pbn_client.const import (
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_client.exceptions import PBNValidationError

from fixtures.pbn_api import (
    MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA,
    MOCK_RETURNED_MONGODB_DATA,
    pbn_pageable_json,
)
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
)
from pbn_api.exceptions import (
    HttpException,
    PKZeroExportDisabled,
    StatementsResendFailedException,
)
from pbn_api.models import Publication, SentData


def _patch_intended_statements(monkeypatch, statements):
    """Patch adapter żeby zwracał zadaną listę intended statements.

    Patchuje OBIE metody adaptera:
    - ``pbn_get_json_statements`` — używana w ``_sync_statements_with_pbn``
      (porównanie z PBN); format ``[{personObjectId, disciplineId, type}, ...]``
    - ``pbn_get_api_statements`` — używana w ``_post_statements_with_retry``
      (POST /v2/statements); zwraca ``{publicationUuid, statements}``

    Ustawia też ``pbn_wysylaj_bez_oswiadczen=True`` na instancji adaptera,
    żeby ``StatementsMissing`` nie wywalił ``pbn_get_json`` w KROK 1
    (walidacja w adapterze wymaga klucza ``statements`` w JSON gdy flaga
    False, a my tu symulujemy różne stany).
    """
    statements_list = list(statements)
    monkeypatch.setattr(
        WydawnictwoPBNAdapter,
        "pbn_get_json_statements",
        lambda self, _lst=None: list(statements_list),
    )
    monkeypatch.setattr(
        WydawnictwoPBNAdapter,
        "pbn_get_api_statements",
        lambda self: {
            "publicationUuid": "00000000-0000-0000-0000-000000000001",
            "statements": list(statements_list),
        },
    )
    original_init = WydawnictwoPBNAdapter.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.pbn_wysylaj_bez_oswiadczen = True

    monkeypatch.setattr(WydawnictwoPBNAdapter, "__init__", patched_init)


def _setup_common_mocks(pbn_client, object_id, pbn_statements=None):
    """Ustawia standardowe odpowiedzi mockowe dla sync_publication flow.

    Mockuje OBA endpointy POST publikacji (``/v1/publications`` +
    ``/v1/repositorium/publications``), download_publication, V2
    institution publications oraz GET statements (pusta lub podana
    lista). Dzięki temu testy nie muszą wiedzieć którą drogą poszedł
    upload (zależy od tego czy ``_patch_intended_statements`` ustawił
    statements puste czy nie).

    Uwaga: ``object_id`` przekazujemy w formacie natywnym (int albo str)
    — PBN GET endpointy formatują URL przez ``.format(id=...)``, a POST
    body dostaje wartość jak jest (typ zachowany dla porównania z
    ``pub.pbn_uid_id`` po sync).
    """
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": object_id}
    ]
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": object_id
    }
    pbn_client.transport.return_values[
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=object_id)
    ] = MOCK_RETURNED_MONGODB_DATA
    pbn_client.transport.return_values[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = (
        MOCK_RETURNED_MONGODB_DATA
    )
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_PUBLICATIONS_V2 + f"?publicationId={object_id}&size=10"
    ] = pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={object_id}&size=5120"
    ] = pbn_pageable_json(list(pbn_statements or []))


# ============================================================
# Podstawowe scenariusze (happy paths) — sync_publication
# ============================================================


@pytest.mark.django_db
def test_sync_publication_to_samo_id(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Publikacja ma już pbn_uid, PBN zwraca to samo ID — pbn_uid_id nie zmienia się."""
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()
    stare_id = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id

    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"
    assert stare_id == pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id


@pytest.mark.django_db
def test_sync_publication_tekstowo_podane_id(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Argument w formacie 'model:pk' jest konwertowany przez eventually_coerce_to_publication."""
    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])

    pbn_client.sync_publication(
        f"wydawnictwo_zwarte:{pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk}"
    )

    pbn_publication.refresh_from_db()
    assert pbn_publication.versions[0]["baz"] == "quux"


@pytest.mark.django_db
def test_sync_publication_nowe_id(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Nowa publikacja bez pbn_uid_id — PBN nadaje ID, ustawiamy lokalnie."""
    assert pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id is None

    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.refresh_from_db()
    # Po refresh_from_db pbn_uid_id to string (CharField PK), mock zwraca
    # int — porównujemy przez str() dla tolerancji typu.
    assert str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid_id) == str(
        pbn_publication.pk
    )


@pytest.mark.django_db
def test_sync_publication_wysylka_z_zerowym_pk(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_uczelnia,
    monkeypatch,
):
    """Flaga ``export_pk_zero`` kontroluje czy prace z PK=0 są wysyłane."""
    pbn_uczelnia.pbn_api_nie_wysylaj_prac_bez_pk = True
    pbn_uczelnia.save()

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.punkty_kbn = 0
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])

    # export_pk_zero=True — pójdzie
    pbn_client.sync_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, export_pk_zero=True
    )

    # export_pk_zero=False — rzuci PKZeroExportDisabled
    with pytest.raises(PKZeroExportDisabled):
        pbn_client.sync_publication(
            pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, export_pk_zero=False
        )


@pytest.mark.django_db
def test_upload_and_sync_publication_without_existing_publication(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, monkeypatch
):
    """Regression: Publication nie istnieje lokalnie przy upload — SentData ma
    być poprawnie zaktualizowany linkiem po download_publication."""
    from fixtures.pbn_api import MOCK_MONGO_ID

    new_object_id = MOCK_MONGO_ID
    assert not Publication.objects.filter(pk=new_object_id).exists()

    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(pbn_client, new_object_id, pbn_statements=[])

    publication = pbn_client.sync_publication(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )

    assert Publication.objects.filter(pk=new_object_id).exists()
    sent_data = SentData.objects.get_for_rec(
        pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    )
    assert sent_data.pbn_uid_id == new_object_id
    assert sent_data.pbn_uid == publication
    assert sent_data.submitted_successfully is True


# ============================================================
# Wybór endpointu na podstawie obecności statements
# ============================================================


@pytest.mark.django_db
def test_sync_publication_bez_statements_idzie_do_repo(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Brak lokalnych statements (flaga uczelni allowed) → endpoint repo."""
    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    assert PBN_POST_PUBLICATION_NO_STATEMENTS_URL in pbn_client.transport.input_values
    assert PBN_POST_PUBLICATIONS_URL not in pbn_client.transport.input_values
    body = pbn_client.transport.input_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL][
        "body"
    ]
    assert isinstance(body, list) and len(body) == 1
    assert "statements" not in body[0]


@pytest.mark.django_db
def test_sync_publication_z_statements_idzie_do_v1_publications(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    monkeypatch,
):
    """Lokalne statements obecne → all-in-one ``/v1/publications`` (raw payload)."""
    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 301,
                "type": "AUTHOR",
            }
        ],
    )
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    assert PBN_POST_PUBLICATIONS_URL in pbn_client.transport.input_values
    assert (
        PBN_POST_PUBLICATION_NO_STATEMENTS_URL not in pbn_client.transport.input_values
    )
    # Body to surowy dict z adaptera (NIE lista) — z kluczem statements.
    body = pbn_client.transport.input_values[PBN_POST_PUBLICATIONS_URL]["body"]
    assert isinstance(body, dict)
    assert "statements" in body


# ============================================================
# Synchronizacja statements: 4 scenariusze (diff + flagi)
# ============================================================


@pytest.mark.django_db
def test_sync_statements_identyczne_nic_nie_wysyla(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    monkeypatch,
):
    """PBN i intencja identyczne — brak DELETE, brak POST /v2/statements."""
    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 301,
                "type": "AUTHOR",
            }
        ],
    )
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    assert url_delete not in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL not in pbn_client.transport.input_values


@pytest.mark.django_db
def test_sync_statements_pbn_puste_bpp_ma_post_only(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    monkeypatch,
):
    """PBN puste, BPP ma intencję — POST do /v2/statements, brak DELETE."""
    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 301,
                "type": "AUTHOR",
            }
        ],
    )
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    assert url_delete not in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL in pbn_client.transport.input_values


@pytest.mark.django_db
def test_sync_statements_pbn_ma_bpp_puste_selektywnie_delete(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    pbn_uczelnia,
    monkeypatch,
):
    """Selektywny mode + PBN ma, BPP puste → DELETE per-osoba, brak POST."""
    pbn_uczelnia.pbn_kasuj_dyscypliny_selektywnie = True
    pbn_uczelnia.save()

    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    pbn_client.transport.return_values[url_delete] = []

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # DELETE wykonany (per osoba) z body {statementsOfPersons: [{personId, role}]}
    assert url_delete in pbn_client.transport.input_values
    body = pbn_client.transport.input_values[url_delete]["body"]
    assert "statementsOfPersons" in body
    assert body["statementsOfPersons"][0]["personId"] == pbn_autor.pbn_uid_id
    assert body["statementsOfPersons"][0]["role"] == "AUTHOR"
    # POST nie ma co robić bo BPP puste
    assert PBN_POST_INSTITUTION_STATEMENTS_URL not in pbn_client.transport.input_values


@pytest.mark.django_db
def test_sync_statements_pbn_ma_bpp_puste_batch_delete(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    pbn_uczelnia,
    monkeypatch,
):
    """Batch mode + PBN ma, BPP puste → delete_all, brak POST."""
    pbn_uczelnia.pbn_kasuj_dyscypliny_selektywnie = False
    pbn_uczelnia.save()

    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    pbn_client.transport.return_values[url_delete] = []

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # Batch DELETE ma body {all: True, statementsOfPersons: []}
    assert url_delete in pbn_client.transport.input_values
    body = pbn_client.transport.input_values[url_delete]["body"]
    assert body == {"all": True, "statementsOfPersons": []}


@pytest.mark.django_db
def test_sync_statements_roznice_selektywnie(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    pbn_uczelnia,
    monkeypatch,
):
    """Różnice w selektywnym trybie: DELETE tylko nieistniejących lokalnie +
    POST brakujących."""
    pbn_uczelnia.pbn_kasuj_dyscypliny_selektywnie = True
    pbn_uczelnia.save()

    # Intencja: autor X z dyscypliną 100
    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 100,
                "type": "AUTHOR",
            }
        ],
    )
    # PBN: ten sam autor X ale z dyscypliną 301
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    pbn_client.transport.return_values[url_delete] = []
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # Klucz (autor, 301) różni się od (autor, 100) → DELETE + POST
    assert url_delete in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL in pbn_client.transport.input_values

    # W selektywnym trybie POST wysyła TYLKO oświadczenia brakujące w PBN
    # (only_in_intended) — nie pełen zestaw BPP. Sprawdzamy że payload
    # zawiera dokładnie jeden statement (autor, dyscyplina 100).
    post_body = pbn_client.transport.input_values[PBN_POST_INSTITUTION_STATEMENTS_URL][
        "body"
    ]
    statements_sent = post_body["data"][0]["statements"]
    assert len(statements_sent) == 1
    assert statements_sent[0]["personObjectId"] == pbn_autor.pbn_uid_id


@pytest.mark.django_db
def test_sync_statements_pbn_subset_bpp_superset_tylko_brakujace(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    pbn_uczelnia,
    monkeypatch,
):
    """PBN = {(A, 301)}, BPP = {(A, 301), (B, 200)} — selektywny tryb.

    ``only_in_pbn`` = ∅ → brak DELETE.
    ``only_in_intended`` = {(B, 200)} → POST tylko (B, 200).

    Weryfikacja że POST nie dubluje (A, 301) który już jest w PBN —
    wysyłamy TYLKO brakujący (B, 200) zgodnie z algorytmem kroku 4b.
    """
    pbn_uczelnia.pbn_kasuj_dyscypliny_selektywnie = True
    pbn_uczelnia.save()

    autor_b_pbn_uid = "autor-B-mongo-id-xxxxxxxxxxxx"

    # Intencja BPP: autor A z dyscypliną 301 + autor B z dyscypliną 200
    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 301,
                "disciplineUuid": "uuid-301",
                "type": "AUTHOR",
            },
            {
                "personObjectId": autor_b_pbn_uid,
                "disciplineId": 200,
                "disciplineUuid": "uuid-200",
                "type": "AUTHOR",
            },
        ],
    )
    # PBN ma tylko autora A z dyscypliną 301 (BPP jest supersetem)
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # DELETE nie wywołany — (A, 301) jest w obu, only_in_pbn puste
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    assert url_delete not in pbn_client.transport.input_values

    # POST wysłany tylko dla (B, 200) — nie dublujemy (A, 301)
    assert PBN_POST_INSTITUTION_STATEMENTS_URL in pbn_client.transport.input_values
    post_body = pbn_client.transport.input_values[PBN_POST_INSTITUTION_STATEMENTS_URL][
        "body"
    ]
    statements_sent = post_body["data"][0]["statements"]
    assert len(statements_sent) == 1
    assert statements_sent[0]["personObjectId"] == autor_b_pbn_uid


@pytest.mark.django_db
def test_sync_statements_pbn_puste_wysyla_wszystkie_w_selektywnym(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_uczelnia,
    monkeypatch,
):
    """Krok 3 algorytmu: PBN puste + BPP ma N oświadczeń → POST zawiera N.

    W selektywnym trybie filter_keys = only_in_intended, które w tym
    scenariuszu = wszystkie klucze BPP (bo PBN jest pusty), więc POST
    wysyła kompletny zestaw BPP — równoważne z "wyślij wszystkie".
    """
    pbn_uczelnia.pbn_kasuj_dyscypliny_selektywnie = True
    pbn_uczelnia.save()

    autor_b_pbn_uid = "autor-B-mongo-id-yyyyyyyyyyyy"
    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 301,
                "disciplineUuid": "uuid-301",
                "type": "AUTHOR",
            },
            {
                "personObjectId": autor_b_pbn_uid,
                "disciplineId": 200,
                "disciplineUuid": "uuid-200",
                "type": "AUTHOR",
            },
        ],
    )
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    assert PBN_POST_INSTITUTION_STATEMENTS_URL in pbn_client.transport.input_values
    post_body = pbn_client.transport.input_values[PBN_POST_INSTITUTION_STATEMENTS_URL][
        "body"
    ]
    statements_sent = post_body["data"][0]["statements"]
    assert len(statements_sent) == 2
    person_ids = {s["personObjectId"] for s in statements_sent}
    assert person_ids == {pbn_autor.pbn_uid_id, autor_b_pbn_uid}


@pytest.mark.django_db
def test_sync_statements_batch_mode_post_wszystkie(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    pbn_uczelnia,
    monkeypatch,
):
    """Batch mode + różnice: delete_all kasuje całość, POST wysyła wszystkie BPP.

    ``kasuj_selektywnie=False`` — po ``delete_all`` PBN jest puste, więc
    mimo że diff dał ``only_in_intended = {nowy}`` i ``only_in_pbn = {stary}``,
    POST musi wysłać PEŁNY zestaw BPP (nie tylko only_in_intended),
    inaczej po delete_all stare oświadczenia znikną bez odtworzenia.
    """
    pbn_uczelnia.pbn_kasuj_dyscypliny_selektywnie = False
    pbn_uczelnia.save()

    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 100,
                "disciplineUuid": "uuid-100",
                "type": "AUTHOR",
            }
        ],
    )
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    pbn_client.transport.return_values[url_delete] = []
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # Batch DELETE wykonany — kasuje wszystko
    body_del = pbn_client.transport.input_values[url_delete]["body"]
    assert body_del == {"all": True, "statementsOfPersons": []}

    # POST wysłał pełen zestaw BPP (tutaj 1 statement — autor z dyscypliną 100),
    # bez filtra ``only_in_intended``. Sprawdzamy że personObjectId i
    # disciplineId pasują do intencji BPP (nie do tego co było w PBN).
    post_body = pbn_client.transport.input_values[PBN_POST_INSTITUTION_STATEMENTS_URL][
        "body"
    ]
    statements_sent = post_body["data"][0]["statements"]
    assert len(statements_sent) == 1
    assert statements_sent[0]["personObjectId"] == pbn_autor.pbn_uid_id


# ============================================================
# Error handling: retry + rollbar + StatementsResendFailedException
# ============================================================


@pytest.mark.django_db
def test_sync_publication_get_statements_retry_wyczerpane_raises(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """GET statements zawodzi 3 razy → StatementsResendFailedException + rollbar."""
    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])
    # Nadpisujemy GET statements żeby rzucał
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = HttpException(500, "/api/v1/.../page/statements", "Server Error")

    # Mock sleep i rollbar żeby test nie był powolny i weryfikujemy call
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    with patch("pbn_api.client.publication_sync.rollbar.report_exc_info") as mock_rb:
        with pytest.raises(StatementsResendFailedException) as exc_info:
            pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # Rollbar wywołany raz z level=warning
    assert mock_rb.called
    call_kwargs = mock_rb.call_args.kwargs
    assert call_kwargs.get("level") == "warning"
    assert "publication_pk" in call_kwargs.get("extra_data", {})
    assert "pbn_uid" in call_kwargs.get("extra_data", {})

    # Exception ma publication_pk i pbn_uid
    assert exc_info.value.pbn_uid == pbn_publication.pk


@pytest.mark.django_db
def test_sync_publication_selektywny_delete_retry_wyczerpane_raises(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    pbn_uczelnia,
    monkeypatch,
):
    """Selektywny DELETE zawodzi 3 razy → StatementsResendFailedException."""
    pbn_uczelnia.pbn_kasuj_dyscypliny_selektywnie = True
    pbn_uczelnia.save()

    _patch_intended_statements(monkeypatch, [])
    _setup_common_mocks(
        pbn_client,
        pbn_publication.pk,
        pbn_statements=[
            {
                "id": "aaa",
                "personId": pbn_autor.pbn_uid_id,
                "area": "301",
                "type": "AUTHOR",
                "institutionId": pbn_jednostka.pbn_uid_id,
            }
        ],
    )
    # DELETE zawsze zawodzi
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    pbn_client.transport.return_values[url_delete] = HttpException(
        500, url_delete, "Server Error"
    )

    monkeypatch.setattr(time, "sleep", lambda *_: None)

    with patch("pbn_api.client.publication_sync.rollbar.report_exc_info"):
        with pytest.raises(StatementsResendFailedException):
            pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


@pytest.mark.django_db
def test_sync_publication_post_v2_statements_retry_wyczerpane_raises(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    monkeypatch,
):
    """POST /v2/statements zawodzi 3 razy → StatementsResendFailedException."""
    _patch_intended_statements(
        monkeypatch,
        [
            {
                "personObjectId": pbn_autor.pbn_uid_id,
                "disciplineId": 100,
                "type": "AUTHOR",
            }
        ],
    )
    _setup_common_mocks(pbn_client, pbn_publication.pk, pbn_statements=[])
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = (
        HttpException(500, PBN_POST_INSTITUTION_STATEMENTS_URL, "Server Error")
    )

    monkeypatch.setattr(time, "sleep", lambda *_: None)

    with patch("pbn_api.client.publication_sync.rollbar.report_exc_info"):
        with pytest.raises(StatementsResendFailedException):
            pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)


# ============================================================
# Edge case: POST publikacji zawodzi — statements nietknięte
# ============================================================


@pytest.mark.django_db
def test_sync_publication_post_repo_fail_statements_nietkniete(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """POST publikacji zawodzi → statements w PBN nie są ruszane."""
    _patch_intended_statements(monkeypatch, [])
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = (
        HttpException(
            500, PBN_POST_PUBLICATION_NO_STATEMENTS_URL, "Internal Server Error"
        )
    )

    with pytest.raises(HttpException):
        pbn_client.sync_publication(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina)

    # Nic nie powinno polecieć do PBN poza failed POST
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    assert url_delete not in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL not in pbn_client.transport.input_values
    assert (
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
        not in pbn_client.transport.input_values
    )


# ============================================================
# Unit test: _diff_statements key mapping
# ============================================================


def test_diff_statements_key_mapping(pbn_client):
    """Klucz porównania PBN vs intended używa (person, discipline) jako string."""
    pbn_stmts = [
        {"personId": "abc123", "area": "301", "type": "AUTHOR"},
        {"personId": "def456", "area": "502", "type": "EDITOR"},
    ]
    intended = [
        {"personObjectId": "abc123", "disciplineId": 301, "type": "AUTHOR"},
        {"personObjectId": "ghi789", "disciplineId": 200, "type": "AUTHOR"},
    ]
    only_pbn, only_intended = pbn_client._diff_statements(pbn_stmts, intended)

    # (abc123, 301) — w obu, więc w żadnym diff
    # (def456, 502) — tylko w PBN
    # (ghi789, 200) — tylko w intended
    assert only_pbn == {("def456", "502")}
    assert only_intended == {("ghi789", "200")}


def test_diff_statements_empty_sets(pbn_client):
    """Puste zestawy → puste diff."""
    only_pbn, only_intended = pbn_client._diff_statements([], [])
    assert only_pbn == set()
    assert only_intended == set()


# ============================================================
# Retry loops: PBNValidationError przerywa natychmiast (bez ponawiania)
# ============================================================


@pytest.mark.django_db
def test_post_statements_with_retry_reraises_validation_immediately(pbn_client, mocker):
    # Walidacja się nie naprawi przez retry — musi przerwać natychmiast.
    exc = PBNValidationError(
        400, "/api/v2/institution-profile/statements", '{"details":{"x":"y"}}'
    )
    mocker.patch.object(
        pbn_client, "_build_post_statements_payload", return_value={"stmt": 1}
    )
    post = mocker.patch.object(
        pbn_client, "post_discipline_statements", side_effect=exc
    )
    report = mocker.patch.object(pbn_client, "_report_statements_failure_and_raise")

    with pytest.raises(PBNValidationError):
        pbn_client._post_statements_with_retry(
            rec=MagicMock(), objectId="123", publication_pk=1
        )

    assert post.call_count == 1  # brak ponawiania
    report.assert_not_called()  # nie raportuje do Rollbara


@pytest.mark.django_db
def test_delete_statements_batch_reraises_validation_immediately(pbn_client, mocker):
    exc = PBNValidationError(
        400, "/api/v2/institution-profile/statements", '{"details":{"x":"y"}}'
    )
    delete = mocker.patch.object(
        pbn_client, "delete_all_publication_statements", side_effect=exc
    )
    report = mocker.patch.object(pbn_client, "_report_statements_failure_and_raise")

    with pytest.raises(PBNValidationError):
        pbn_client._delete_statements_batch("123", publication_pk=1)

    assert delete.call_count == 1
    report.assert_not_called()


@pytest.mark.django_db
def test_delete_statements_selective_reraises_validation_immediately(
    pbn_client, mocker
):
    exc = PBNValidationError(
        400, "/api/v2/institution-profile/statements", '{"details":{"x":"y"}}'
    )
    delete = mocker.patch.object(
        pbn_client, "delete_publication_statement", side_effect=exc
    )
    report = mocker.patch.object(pbn_client, "_report_statements_failure_and_raise")

    with pytest.raises(PBNValidationError):
        pbn_client._delete_statements_selective(
            "123", [{"personId": "p1", "type": "AUTHOR"}], publication_pk=1
        )

    assert delete.call_count == 1  # brak ponawiania
    report.assert_not_called()
