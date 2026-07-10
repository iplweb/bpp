"""Tests for ``DSpaceProvider.split_input`` — wykrywanie stron-list
(kolekcja/community/discover/search) i enumeracja ich itemów przez REST,
oraz rozszerzenie ``validate_identifier`` o akceptację takich URL-i.

Cały HTTP jest mockowany (``requests.get`` w module ``dspace``) — brak
połączeń do żywej sieci. Kształty odpowiedzi REST (DSpace 6 ``/rest/...``
i DSpace 7 ``/server/api/discover/search/objects``) zweryfikowano na
żywo na ``dspace.piwet.pulawy.pl`` (DSpace 6 XMLUI) i
``repozytorium.wsb-nlu.edu.pl`` (DSpace 7+ Angular UI) podczas budowy tego
providera — patrz PR/handoff.
"""

from unittest.mock import patch

import requests

from importer_publikacji.providers import SplitRecord
from importer_publikacji.providers.dspace import DSpaceProvider

from ._dspace_provider_samples import (
    BASE_URL,
    SAMPLE_HANDLE_URL,
    SAMPLE_URL,
    _mock_response,
)

OLD_BASE = "https://dspace.piwet.pulawy.pl"
OLD_COLLECTION_HANDLE_URL = f"{OLD_BASE}/handle/123456789/6"
OLD_COLLECTION_UUID = "09e84d85-18d7-41f9-b339-d65d87f35c56"
OLD_COMMUNITY_HANDLE_URL = f"{OLD_BASE}/handle/123456789/5"
OLD_COMMUNITY_UUID = "118f19ee-907d-4084-9a98-ef6dc526b712"

NEW_COLLECTION_UUID = "d7d434e3-794c-4e84-b2b9-6b2767665644"
NEW_COLLECTION_URL = f"{BASE_URL}/collections/{NEW_COLLECTION_UUID}"
NEW_COMMUNITY_URL = f"{BASE_URL}/communities/{NEW_COLLECTION_UUID}"
NEW_SEARCH_URL = f"{BASE_URL}/search?query=test&scope={NEW_COLLECTION_UUID}"


def _hal_discover_page(objects, total_pages=1):
    return _mock_response(
        {
            "_embedded": {
                "searchResult": {
                    "page": {
                        "number": 0,
                        "size": 20,
                        "totalPages": total_pages,
                        "totalElements": len(objects),
                    },
                    "_embedded": {
                        "objects": [
                            {"_embedded": {"indexableObject": obj}} for obj in objects
                        ]
                    },
                }
            }
        }
    )


# --- (a) DSpace 6 (old): kolekcja/community handle -> enumeracja REST ---


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_old_dspace_collection_returns_n_records(mock_get):
    handle_resp = _mock_response(
        {"type": "collection", "uuid": OLD_COLLECTION_UUID, "handle": "123456789/6"}
    )
    items_resp = _mock_response(
        [
            {"uuid": "u1", "handle": "123456789/58", "name": "Praca 1"},
            {"uuid": "u2", "handle": "123456789/59", "name": "Praca 2"},
            {"uuid": "u3", "handle": "123456789/60", "name": "Praca 3"},
        ]
    )
    mock_get.side_effect = [handle_resp, items_resp]

    records = DSpaceProvider().split_input(OLD_COLLECTION_HANDLE_URL)

    assert len(records) == 3
    assert all(r.ok for r in records)
    assert records[0].raw == f"{OLD_BASE}/handle/123456789/58"
    assert records[0].title == "Praca 1"
    assert records[1].raw == f"{OLD_BASE}/handle/123456789/59"
    assert records[2].raw == f"{OLD_BASE}/handle/123456789/60"
    assert records[2].title == "Praca 3"

    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].args[0] == f"{OLD_BASE}/rest/handle/123456789/6"
    assert (
        mock_get.call_args_list[1].args[0]
        == f"{OLD_BASE}/rest/collections/{OLD_COLLECTION_UUID}/items"
    )


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_old_dspace_collection_paginates(mock_get):
    """Kolekcja z wiecej niz jedna strona wynikow — druga strona krotsza
    niz limit => petla konczy sie naturalnie (bez zapytan w nieskonczonosc).
    """
    handle_resp = _mock_response(
        {"type": "collection", "uuid": OLD_COLLECTION_UUID, "handle": "123456789/6"}
    )
    page1 = _mock_response(
        [
            {"uuid": f"u{i}", "handle": f"123456789/{i}", "name": f"P{i}"}
            for i in range(100)
        ]
    )
    page2 = _mock_response(
        [{"uuid": "u100", "handle": "123456789/100", "name": "Ostatnia"}]
    )
    mock_get.side_effect = [handle_resp, page1, page2]

    records = DSpaceProvider().split_input(OLD_COLLECTION_HANDLE_URL)

    assert len(records) == 101
    assert records[-1].title == "Ostatnia"
    assert mock_get.call_count == 3


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_old_dspace_community_returns_items_from_all_collections(mock_get):
    collections_resp = _mock_response(
        [
            {"uuid": "col-a", "handle": "123456789/347"},
            {"uuid": "col-b", "handle": "123456789/12"},
        ]
    )
    items_a = _mock_response(
        [{"uuid": "ia1", "handle": "123456789/900", "name": "Item A1"}]
    )
    items_b = _mock_response(
        [{"uuid": "ib1", "handle": "123456789/901", "name": "Item B1"}]
    )
    handle_resp = _mock_response(
        {"type": "community", "uuid": OLD_COMMUNITY_UUID, "handle": "123456789/5"}
    )
    mock_get.side_effect = [handle_resp, collections_resp, items_a, items_b]

    records = DSpaceProvider().split_input(OLD_COMMUNITY_HANDLE_URL)

    assert len(records) == 2
    assert {r.raw for r in records} == {
        f"{OLD_BASE}/handle/123456789/900",
        f"{OLD_BASE}/handle/123456789/901",
    }


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_old_dspace_collection_rest_error_falls_back_to_single(mock_get):
    handle_resp = _mock_response(
        {"type": "collection", "uuid": OLD_COLLECTION_UUID, "handle": "123456789/6"}
    )
    mock_get.side_effect = [handle_resp, requests.exceptions.ConnectionError()]

    records = DSpaceProvider().split_input(OLD_COLLECTION_HANDLE_URL)

    assert records == [SplitRecord(raw=OLD_COLLECTION_HANDLE_URL)]


# --- (b) DSpace 7+ (new): discover/search -> enumeracja REST ---


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_new_dspace_discover_returns_n_records(mock_get):
    mock_get.return_value = _hal_discover_page(
        [
            {"uuid": "aaa1", "handle": "11199/1", "name": "Item A"},
            {"uuid": "bbb2", "handle": "11199/2", "name": "Item B"},
        ]
    )

    records = DSpaceProvider().split_input(NEW_SEARCH_URL)

    assert len(records) == 2
    assert records[0].raw == f"{BASE_URL}/items/aaa1"
    assert records[0].title == "Item A"
    assert records[1].raw == f"{BASE_URL}/items/bbb2"

    call = mock_get.call_args_list[0]
    assert call.args[0] == f"{BASE_URL}/server/api/discover/search/objects"
    assert call.kwargs["params"]["dsoType"] == "item"
    assert call.kwargs["params"]["scope"] == NEW_COLLECTION_UUID
    assert call.kwargs["params"]["query"] == "test"


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_new_dspace_collection_url_returns_n_records(mock_get):
    mock_get.return_value = _hal_discover_page(
        [{"uuid": "ccc3", "handle": "11199/3", "name": "Item C"}]
    )

    records = DSpaceProvider().split_input(NEW_COLLECTION_URL)

    assert len(records) == 1
    assert records[0].raw == f"{BASE_URL}/items/ccc3"
    call = mock_get.call_args_list[0]
    assert call.kwargs["params"]["scope"] == NEW_COLLECTION_UUID


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_new_dspace_community_url_returns_n_records(mock_get):
    mock_get.return_value = _hal_discover_page(
        [{"uuid": "ddd4", "handle": "11199/4", "name": "Item D"}]
    )

    records = DSpaceProvider().split_input(NEW_COMMUNITY_URL)

    assert len(records) == 1
    assert records[0].raw == f"{BASE_URL}/items/ddd4"


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_new_dspace_discover_paginates(mock_get):
    page1 = _hal_discover_page(
        [{"uuid": f"u{i}", "handle": f"11199/{i}", "name": f"P{i}"} for i in range(20)],
        total_pages=2,
    )
    page2 = _hal_discover_page(
        [{"uuid": "u20", "handle": "11199/20", "name": "Ostatni"}],
        total_pages=2,
    )
    mock_get.side_effect = [page1, page2]

    records = DSpaceProvider().split_input(NEW_COLLECTION_URL)

    assert len(records) == 21
    assert records[-1].title == "Ostatni"
    assert mock_get.call_count == 2


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_new_dspace_discover_rest_error_falls_back_to_single(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError()

    records = DSpaceProvider().split_input(NEW_COLLECTION_URL)

    assert records == [SplitRecord(raw=NEW_COLLECTION_URL)]


# --- (c) pojedynczy item -> dokladnie 1 rekord (fallthrough) ---


def test_split_input_dspace7_item_url_returns_single_record_no_network():
    records = DSpaceProvider().split_input(SAMPLE_URL)
    assert records == [SplitRecord(raw=SAMPLE_URL)]


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_dspace6_item_handle_returns_single_record(mock_get):
    mock_get.return_value = _mock_response(
        {"type": "item", "uuid": "some-item-uuid", "handle": "123456789/922"}
    )

    records = DSpaceProvider().split_input(SAMPLE_HANDLE_URL)

    assert records == [SplitRecord(raw=SAMPLE_HANDLE_URL)]
    mock_get.assert_called_once_with(
        f"{OLD_BASE}/rest/handle/123456789/922",
        timeout=15,
    )


@patch("importer_publikacji.providers.dspace.requests.get")
def test_split_input_dspace6_handle_type_network_error_falls_through(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError()

    records = DSpaceProvider().split_input(SAMPLE_HANDLE_URL)

    assert records == [SplitRecord(raw=SAMPLE_HANDLE_URL)]


def test_split_input_garbage_returns_single_record_no_network():
    records = DSpaceProvider().split_input("not a url")
    assert records == [SplitRecord(raw="not a url")]


def test_split_input_empty_string():
    records = DSpaceProvider().split_input("")
    assert records == [SplitRecord(raw="")]


# --- (d) validate_identifier: akceptacja list, odrzucenie smieci ---


def test_validate_identifier_accepts_new_dspace_collection_url():
    p = DSpaceProvider()
    assert p.validate_identifier(NEW_COLLECTION_URL) == NEW_COLLECTION_URL


def test_validate_identifier_accepts_new_dspace_community_url():
    p = DSpaceProvider()
    assert p.validate_identifier(NEW_COMMUNITY_URL) == NEW_COMMUNITY_URL


def test_validate_identifier_accepts_new_dspace_search_url():
    p = DSpaceProvider()
    result = p.validate_identifier(NEW_SEARCH_URL)
    assert result is not None
    assert result.startswith(f"{BASE_URL}/search?")
    assert "query=test" in result
    assert f"scope={NEW_COLLECTION_UUID}" in result


def test_validate_identifier_accepts_new_dspace_browse_url():
    p = DSpaceProvider()
    url = f"{BASE_URL}/browse/title?scope={NEW_COLLECTION_UUID}"
    result = p.validate_identifier(url)
    assert result is not None
    assert f"scope={NEW_COLLECTION_UUID}" in result


def test_validate_identifier_accepts_old_dspace_collection_handle_url():
    """Handle URL kolekcji DSpace 6 juz dzis przechodzi regex (item i
    kolekcja dziela ten sam ksztalt URL) — potwierdzamy ze dalej dziala,
    routing item/lista dzieje sie pozniej w split_input."""
    p = DSpaceProvider()
    assert p.validate_identifier(OLD_COLLECTION_HANDLE_URL) == OLD_COLLECTION_HANDLE_URL


def test_validate_identifier_still_rejects_garbage():
    p = DSpaceProvider()
    assert p.validate_identifier("not a url") is None
    assert p.validate_identifier("") is None
    assert p.validate_identifier(f"{BASE_URL}/some/random/path") is None


# --- fetch(): siatka bezpieczenstwa gdy lista ma dokladnie 1 wynik ---
#
# FetchView.post (views/wizard.py) idzie sciezka pojedynczej sesji, gdy
# split_input() zwroci < 2 rekordy — z identifier=<oryginalny URL listy>,
# nie URL itemu. fetch() musi wiec sam sobie poradzic z takim URL-em.


@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_resolves_single_item_new_dspace_collection_via_rest(mock_get):
    """Kolekcja DSpace 7+ z dokladnie 1 wynikiem, trafiajaca do fetch()
    bezposrednio (patrz docstring _resolve_single_item_from_list) —
    rozwiazuje sie do prawdziwego itemu (REST /collections/{uuid} ma
    odrebny ksztalt URL od /items/{uuid}, wiec _parse_dspace_url() od
    razu zwraca None i uruchamia siatke bezpieczenstwa)."""
    discover_resp = _hal_discover_page(
        [
            {
                "uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "handle": "11199/999",
                "name": "Jedyna praca",
            }
        ]
    )
    item_fetch_resp = _mock_response(
        {
            "uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "metadata": {"dc.title": [{"value": "Jedyna praca"}]},
        }
    )
    mock_get.side_effect = [discover_resp, item_fetch_resp]

    pub = DSpaceProvider().fetch(NEW_COLLECTION_URL)

    assert pub is not None
    assert pub.title == "Jedyna praca"
    # Ostatnie wywolanie (rzeczywisty fetch) musi trafic w URL itemu,
    # nie w oryginalny URL kolekcji.
    assert mock_get.call_args_list[-1].args[0] == (
        f"{BASE_URL}/server/api/core/items/f47ac10b-58cc-4372-a567-0e02b2c3d479"
    )


@patch(
    "importer_publikacji.providers.dspace._fallback_to_www",
    return_value=None,
)
@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_single_item_new_collection_www_fallback_targets_item(
    mock_get, mock_fallback
):
    """Gdy REST fetch itemu (rozwiazanego z kolekcji 1-elementowej)
    zawiedzie, WWW fallback ma probowac URL itemu — nie URL-a
    oryginalnej kolekcji (ktorej HTML nie ma metadanych publikacji)."""
    discover_resp = _hal_discover_page(
        [
            {
                "uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "handle": "11199/999",
                "name": "Jedyna praca",
            }
        ]
    )
    item_fetch_resp = _mock_response({}, status_code=404)
    mock_get.side_effect = [discover_resp, item_fetch_resp]

    pub = DSpaceProvider().fetch(NEW_COLLECTION_URL)

    assert pub is None
    mock_fallback.assert_called_once_with(
        f"{BASE_URL}/items/f47ac10b-58cc-4372-a567-0e02b2c3d479"
    )


@patch(
    "importer_publikacji.providers.dspace._fallback_to_www",
    return_value=None,
)
@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_old_dspace_single_item_collection_known_limitation(
    mock_get, mock_fallback
):
    """Znane, udokumentowane ograniczenie: handle w DSpace 6 XMLUI jest
    niejednoznaczny (ten sam ksztalt URL dla itemu i kolekcji), a
    fetch() na POJEDYNCZYM URL-u celowo NIE robi dodatkowego zapytania
    REST "jaki to typ" przed proba pobrania — kontrakt "1 zapytanie REST
    per fetch" dla zwyklego itemu jest juz zagwarantowany istniejacym
    testem (test_fetch_dspace6_success, ktory sprawdza
    assert_called_once_with). Dla ekstremalnie rzadkiego przypadku
    kolekcji z DOKLADNIE 1 pozycja trafiajacej do fetch() bezposrednio
    (FetchView.post, sciezka pojedynczej sesji gdy split_input() zwrocil
    < 2 rekordy), fetch() nadal probuje pobrac kolekcje jak item — REST
    zwroci pusty tytul (kolekcje nie maja dc.title), wiec konczy sie na
    WWW-fallbacku strony kolekcji (bez metadanych publikacji). To
    zachowanie jest identyczne z tym sprzed tej zmiany — nie regresja,
    tylko nieusunieta w tym PR (dla DSpace 7+ analogiczny przypadek JEST
    poprawnie obsluzony, patrz
    test_fetch_resolves_single_item_new_dspace_collection_via_rest, bo
    /collections/{uuid} ma odrebny ksztalt URL od /items/{uuid})."""
    collection_resp = _mock_response({"handle": "123456789/6", "metadata": []})
    mock_get.return_value = collection_resp

    pub = DSpaceProvider().fetch(OLD_COLLECTION_HANDLE_URL)

    assert pub is None
    mock_fallback.assert_called_once_with(OLD_COLLECTION_HANDLE_URL)


def test_fetch_garbage_returns_none_no_network():
    assert DSpaceProvider().fetch("not a valid url") is None
