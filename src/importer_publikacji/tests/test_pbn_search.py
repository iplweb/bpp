"""Testy modułu wyszukiwania odpowiednika PBN (krok „Sprawdź w PBN")."""

from unittest.mock import MagicMock

import pytest

from importer_publikacji.views.pbn_search import (
    AXIS_DOI,
    AXIS_TITLE,
    AXIS_WWW,
    _clear_pbn_equivalent,
    _dedup_by_mongo_id,
    _extract_object,
    _normalize_www,
    _operator_pbn_logged_in,
    _result_from_search_elem,
    _search_pbn_equivalents,
    _select_pbn_equivalent,
)
from pbn_api.exceptions import (
    NeedsPBNAuthorisationException,
    PraceSerwisoweException,
)

# --- _operator_pbn_logged_in -------------------------------------------------


def test_operator_logged_in_true():
    user = MagicMock()
    user.pbn_token = "tok"
    user.pbn_token_possibly_valid.return_value = True
    assert _operator_pbn_logged_in(user) is True


def test_operator_logged_in_no_token():
    user = MagicMock()
    user.pbn_token = ""
    assert _operator_pbn_logged_in(user) is False


def test_operator_logged_in_token_expired():
    user = MagicMock()
    user.pbn_token = "tok"
    user.pbn_token_possibly_valid.return_value = False
    assert _operator_pbn_logged_in(user) is False


def test_operator_logged_in_none_user():
    assert _operator_pbn_logged_in(None) is False


# --- _normalize_www ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://example.com/a/", "example.com/a"),
        ("http://example.com", "example.com"),
        ("  https://EXAMPLE.com/x  ", "EXAMPLE.com/x"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_www(raw, expected):
    assert _normalize_www(raw) == expected


# --- _extract_object ---------------------------------------------------------


def test_extract_object_from_versions():
    elem = {
        "mongoId": "x",
        "versions": [
            {"current": False, "object": {"title": "stary"}},
            {"current": True, "object": {"title": "nowy", "doi": "10.1/x"}},
        ],
    }
    obj = _extract_object(elem)
    assert obj["title"] == "nowy"
    assert obj["doi"] == "10.1/x"


def test_extract_object_flat_fallback():
    elem = {"mongoId": "x", "title": "plaski"}
    assert _extract_object(elem) == elem


# --- _result_from_search_elem ------------------------------------------------


def test_result_from_search_elem_nested():
    elem = {
        "mongoId": "abc",
        "versions": [
            {"current": True, "object": {"title": "T", "doi": "10.1/x", "year": 2020}}
        ],
    }
    uczelnia = MagicMock()
    uczelnia.pbn_api_root = "https://pbn.example"
    r = _result_from_search_elem(elem, AXIS_DOI, uczelnia)
    assert r["mongo_id"] == "abc"
    assert r["title"] == "T"
    assert r["doi"] == "10.1/x"
    assert r["year"] == 2020
    assert r["axis"] == AXIS_DOI
    assert "abc" in r["pbn_url"]


# --- _dedup_by_mongo_id ------------------------------------------------------


def test_dedup_by_mongo_id():
    results = [
        {"mongo_id": "a"},
        {"mongo_id": "a"},
        {"mongo_id": "b"},
        {"mongo_id": None},
    ]
    out = _dedup_by_mongo_id(results)
    assert [r["mongo_id"] for r in out] == ["a", "b"]


# --- _search_pbn_equivalents (mock client) -----------------------------------


def _make_session(doi="10.1/x", title="Tytuł pracy", url=None):
    session = MagicMock()
    session.normalized_data = {"doi": doi, "title": title, "url": url}
    return session


def _elem(mongo_id, title="T", doi="", year=2020):
    return {
        "mongoId": mongo_id,
        "versions": [
            {"current": True, "object": {"title": title, "doi": doi, "year": year}}
        ],
    }


def test_search_equivalents_doi_and_title():
    session = _make_session()
    user = MagicMock()
    user.pbn_token = "tok"

    client = MagicMock()

    def _search(**kw):
        if "doi" in kw:
            return [_elem("doi1", doi="10.1/x")]
        if "title" in kw:
            return [_elem("t1"), _elem("t2")]
        return []

    client.search_publications.side_effect = _search
    session.uczelnia.pbn_client.return_value = client

    res = _search_pbn_equivalents(session, user)

    assert [r["mongo_id"] for r in res["by_doi"]] == ["doi1"]
    assert [r["mongo_id"] for r in res["by_title"]] == ["t1", "t2"]
    assert res["by_title"][0]["axis"] == AXIS_TITLE
    assert res["by_www"] == []
    assert res["total_unique"] == 3
    assert res["error"] is None
    assert res["needs_auth"] is False
    # NIE dodajemy type= do wyszukiwania serwerowego
    for call in client.search_publications.call_args_list:
        assert "type" not in call.kwargs


def test_search_equivalents_limit_10_per_axis():
    session = _make_session(doi=None, title="wiele")
    user = MagicMock()
    user.pbn_token = "tok"

    client = MagicMock()
    # 25 wyników — oczekujemy ucięcia do 10
    client.search_publications.return_value = [_elem(f"m{i}") for i in range(25)]
    session.uczelnia.pbn_client.return_value = client

    res = _search_pbn_equivalents(session, user)
    assert len(res["by_title"]) == 10


def test_search_equivalents_needs_auth():
    session = _make_session()
    user = MagicMock()
    user.pbn_token = "tok"

    client = MagicMock()
    client.search_publications.side_effect = NeedsPBNAuthorisationException(
        403, "/api/", "auth"
    )
    session.uczelnia.pbn_client.return_value = client

    res = _search_pbn_equivalents(session, user)
    assert res["needs_auth"] is True


def test_search_equivalents_prace_serwisowe():
    session = _make_session()
    user = MagicMock()
    user.pbn_token = "tok"

    client = MagicMock()
    client.search_publications.side_effect = PraceSerwisoweException()
    session.uczelnia.pbn_client.return_value = client

    res = _search_pbn_equivalents(session, user)
    assert "serwisow" in (res["error"] or "").lower()


def test_search_equivalents_no_uczelnia_still_returns():
    session = _make_session()
    session.uczelnia = None
    user = MagicMock()
    user.pbn_token = "tok"

    res = _search_pbn_equivalents(session, user)
    assert res["by_doi"] == []
    assert res["by_title"] == []
    assert res["total_unique"] == 0


# --- oś WWW z lokalnego cache ------------------------------------------------


@pytest.mark.django_db
def test_search_equivalents_www_local_cache():
    from model_bakery import baker

    from pbn_api.models import Publication

    baker.make(
        Publication,
        mongoId="www1",
        title="Praca WWW",
        publicUri="http://onet.pl/artykul",
    )

    session = MagicMock()
    session.normalized_data = {
        "doi": None,
        "title": None,
        "url": "https://onet.pl/artykul/",
    }
    session.uczelnia = None
    user = MagicMock()
    user.pbn_token = ""

    res = _search_pbn_equivalents(session, user)
    assert [r["mongo_id"] for r in res["by_www"]] == ["www1"]
    assert res["by_www"][0]["axis"] == AXIS_WWW


# --- _select_pbn_equivalent / _clear_pbn_equivalent --------------------------


def test_clear_pbn_equivalent():
    session = MagicMock()
    session.matched_data = {"pbn_mongo_id": "x", "punkty_kbn": "5"}
    _clear_pbn_equivalent(session)
    assert "pbn_mongo_id" not in session.matched_data
    assert session.matched_data["punkty_kbn"] == "5"


def test_select_pbn_equivalent_empty_mongo_id():
    session = MagicMock()
    session.matched_data = {}
    user = MagicMock()
    assert _select_pbn_equivalent(session, user, "") is False
    assert "pbn_mongo_id" not in session.matched_data


def test_select_pbn_equivalent_downloads_and_sets(monkeypatch):
    session = MagicMock()
    session.matched_data = {}
    client = MagicMock()
    client.get_publication_by_id.return_value = {"mongoId": "dl1"}
    session.uczelnia.pbn_client.return_value = client
    user = MagicMock()
    user.pbn_token = "tok"

    monkeypatch.setattr(
        "pbn_integrator.utils.zapisz_mongodb",
        lambda data, model: None,
    )

    assert _select_pbn_equivalent(session, user, "dl1") is True
    assert session.matched_data["pbn_mongo_id"] == "dl1"


@pytest.mark.django_db
def test_select_pbn_equivalent_falls_back_to_local(monkeypatch):
    from model_bakery import baker

    from pbn_api.models import Publication

    baker.make(Publication, mongoId="local1", title="X")

    session = MagicMock()
    session.matched_data = {}
    # Klient PBN nie działa (brak konfiguracji) — ale rekord jest lokalnie.
    session.uczelnia.pbn_client.side_effect = Exception("brak konfiguracji")
    user = MagicMock()
    user.pbn_token = "tok"

    assert _select_pbn_equivalent(session, user, "local1") is True
    assert session.matched_data["pbn_mongo_id"] == "local1"
