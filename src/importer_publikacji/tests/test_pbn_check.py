from unittest.mock import MagicMock, patch

import pytest

from importer_publikacji.views import (
    _check_pbn_by_doi,
    _empty_pbn_result,
    _ensure_pbn_publication_local,
    _get_pbn_publication_by_doi,
    _link_pbn_uid,
    _populate_pbn_result,
)
from pbn_api.exceptions import (
    AccessDeniedException,
    HttpException,
    NeedsPBNAuthorisationException,
    PraceSerwisoweException,
)


def _make_session(
    provider_name="CrossRef",
    doi="10.1234/test",
    matched_data=None,
):
    session = MagicMock()
    session.provider_name = provider_name
    session.normalized_data = {"doi": doi} if doi else {}
    session.matched_data = matched_data or {}
    return session


def test_check_pbn_skip_when_provider_is_pbn():
    session = _make_session(provider_name="PBN")
    assert _check_pbn_by_doi(session) is None


def test_check_pbn_skip_when_no_doi():
    session = _make_session(doi=None)
    assert _check_pbn_by_doi(session) is None


def test_check_pbn_skip_when_empty_doi():
    session = _make_session(doi="")
    assert _check_pbn_by_doi(session) is None


def test_check_pbn_skip_when_client_fails():
    # W views.py ``_get_pbn_client`` jest importowany lokalnie w ciele
    # ``_check_pbn_by_doi`` (from .providers.pbn import _get_pbn_client) —
    # nie jest atrybutem modułu ``importer_publikacji.views`` i nie można
    # go zpatchować przez "importer_publikacji.views._get_pbn_client".
    # Patchujemy u źródła (``importer_publikacji.providers.pbn``), co
    # jest równoważne — lokalny import złapie zpatchowaną wersję.
    with patch(
        "importer_publikacji.providers.pbn._get_pbn_client",
        side_effect=ValueError("Brak konfiguracji"),
    ):
        session = _make_session()
        assert _check_pbn_by_doi(session) is None


def test_get_pbn_publication_by_doi_success():
    client = MagicMock()
    client.get_publication_by_doi.return_value = {
        "mongoId": "abc123def456",
        "status": "ACTIVE",
    }
    data, error = _get_pbn_publication_by_doi(client, "10.1234/test")
    assert data == {"mongoId": "abc123def456", "status": "ACTIVE"}
    assert error is None


def test_get_pbn_publication_by_doi_404():
    client = MagicMock()
    client.get_publication_by_doi.side_effect = HttpException(
        404, "/api/v1/publications/doi/", "Not found"
    )
    data, error = _get_pbn_publication_by_doi(client, "10.1234/test")
    assert data is None
    assert error is not None
    assert error["pbn_error"] is None
    assert error["pbn_needs_auth"] is False


def test_get_pbn_publication_by_doi_access_denied():
    client = MagicMock()
    client.get_publication_by_doi.side_effect = AccessDeniedException(
        "/api/v1/", "Forbidden"
    )
    data, error = _get_pbn_publication_by_doi(client, "10.1234/test")
    assert data is None
    assert error["pbn_needs_auth"] is True


def test_get_pbn_publication_by_doi_needs_auth():
    client = MagicMock()
    client.get_publication_by_doi.side_effect = NeedsPBNAuthorisationException(
        403, "/api/", "Auth"
    )
    data, error = _get_pbn_publication_by_doi(client, "10.1234/test")
    assert data is None
    assert error["pbn_needs_auth"] is True


def test_get_pbn_publication_by_doi_prace_serwisowe():
    client = MagicMock()
    client.get_publication_by_doi.side_effect = PraceSerwisoweException()
    data, error = _get_pbn_publication_by_doi(client, "10.1234/test")
    assert data is None
    assert error["pbn_error"] == "PBN w trakcie prac serwisowych"


def test_get_pbn_publication_by_doi_http_500():
    client = MagicMock()
    client.get_publication_by_doi.side_effect = HttpException(
        500, "/api/", "Server Error"
    )
    data, error = _get_pbn_publication_by_doi(client, "10.1234/test")
    assert data is None
    assert "Błąd komunikacji z PBN" in error["pbn_error"]


def test_empty_pbn_result():
    result = _empty_pbn_result()
    assert result["pbn_mongo_id"] is None
    assert result["pbn_url"] is None
    assert result["pbn_error"] is None
    assert result["pbn_needs_auth"] is False


@pytest.mark.django_db
# ``_populate_pbn_result`` i ``_ensure_pbn_publication_local`` żyją razem
# w pod-module ``importer_publikacji.views.pbn_check`` (po podziale views.py
# na pakiet). Wywołanie z ``_populate_pbn_result`` rozwiązuje się przez
# globals pod-modułu, więc patchujemy tam — patch na re-eksporcie
# ``importer_publikacji.views._ensure_pbn_publication_local`` nie miałby
# efektu, identycznie jak udokumentowano wyżej dla ``_get_pbn_client``.
@patch("importer_publikacji.views.pbn_check._ensure_pbn_publication_local")
def test_populate_pbn_result_with_data(mock_ensure):
    session = _make_session()
    result = _empty_pbn_result()
    data = {"mongoId": "abc123def456", "status": "ACTIVE"}

    _populate_pbn_result(result, data, session)

    assert result["pbn_mongo_id"] == "abc123def456"
    assert session.matched_data["pbn_mongo_id"] == "abc123def456"
    session.save.assert_called_once()
    mock_ensure.assert_called_once_with(data)


def test_populate_pbn_result_with_empty_data():
    session = _make_session()
    result = _empty_pbn_result()
    _populate_pbn_result(result, None, session)
    assert result["pbn_mongo_id"] is None


def test_populate_pbn_result_no_mongo_id():
    session = _make_session()
    result = _empty_pbn_result()
    _populate_pbn_result(result, {"status": "ACTIVE"}, session)
    assert result["pbn_mongo_id"] is None


@patch("pbn_integrator.utils.zapisz_mongodb")
def test_ensure_pbn_publication_local_calls_zapisz(
    mock_zapisz,
):
    data = {
        "mongoId": "abc123",
        "status": "ACTIVE",
        "verificationLevel": "MODERATOR",
        "verified": True,
        "versions": [],
    }
    _ensure_pbn_publication_local(data)
    mock_zapisz.assert_called_once()


@patch("pbn_integrator.utils.zapisz_mongodb")
def test_ensure_pbn_publication_local_handles_error(
    mock_zapisz,
):
    mock_zapisz.side_effect = Exception("DB error")
    # Nie powinno rzucić wyjątku
    _ensure_pbn_publication_local({"mongoId": "abc123"})


@pytest.mark.django_db
def test_link_pbn_uid_no_mongo_id():
    session = _make_session(matched_data={})
    record = MagicMock()
    _link_pbn_uid(session, record)
    record.save.assert_not_called()


@pytest.mark.django_db
def test_link_pbn_uid_publication_not_found():
    session = _make_session(matched_data={"pbn_mongo_id": "nonexistent123456789012"})
    record = MagicMock()
    _link_pbn_uid(session, record)
    record.save.assert_not_called()
