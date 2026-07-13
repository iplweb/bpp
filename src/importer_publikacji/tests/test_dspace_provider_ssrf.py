"""Testy guardu SSRF providera DSpace (H2).

``_fetch_dspace7``/``_fetch_dspace6`` pobierają metadane po stronie serwera z
adresu wyprowadzonego wprost z URL-a podanego przez użytkownika. Muszą — tak
jak provider WWW — odmówić uderzenia w adresy loopback/prywatne/link-local
(w tym metadata cloud 169.254.169.254). Wcześniej DSpace omijał istniejący
guard SSRF (``www.network._host_is_safe``), wołając ``requests.get`` bez
żadnej walidacji hosta i z domyślnym ``allow_redirects=True``.
"""

from unittest.mock import MagicMock

import pytest

from importer_publikacji.providers import dspace
from importer_publikacji.providers.www import network

UUID = "00000000-0000-0000-0000-000000000000"


def _resolve_to(ip):
    """Podmianka ``_resolve_ips``: każdy host rozwiązuje się na dany IP."""
    return lambda hostname: [ip]


def _benign_get():
    """Mock ``requests.get`` zwracający nieszkodliwą, pustą odpowiedź DSpace
    (brak ``dc.title`` → fetch i tak zwróci None). Dzięki temu jedynym
    sygnałem podatności jest to, czy ``get`` W OGÓLE został wywołany."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.json.return_value = {"metadata": []}
    resp.iter_content = lambda chunk_size=1: iter([b'{"metadata": []}'])
    return MagicMock(return_value=resp)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # prywatna 10/8
        "169.254.169.254",  # metadata cloud (link-local)
        "::1",  # loopback v6
    ],
)
def test_dspace7_fetch_blocks_internal_host(monkeypatch, ip):
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to(ip))
    get = _benign_get()
    monkeypatch.setattr(network.requests, "get", get)

    assert dspace._fetch_dspace7("http://repo.internal", UUID) is None
    get.assert_not_called()


def test_dspace6_fetch_blocks_internal_host(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("169.254.169.254"))
    get = _benign_get()
    monkeypatch.setattr(network.requests, "get", get)

    assert dspace._fetch_dspace6("http://repo.internal", "123456789/1") is None
    get.assert_not_called()


def test_dspace_provider_fetch_rejects_internal_url(monkeypatch):
    """Pełna ścieżka providera: URL na loopback nie może w ogóle wywołać
    ``requests.get`` — ani przez DSpace REST API, ani przez fallback WWW
    (który ma własny guard ``_validate_url``)."""
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("127.0.0.1"))
    get = _benign_get()
    monkeypatch.setattr(network.requests, "get", get)

    url = f"http://127.0.0.1/items/{UUID}"
    assert dspace.DSpaceProvider().fetch(url) is None
    get.assert_not_called()


def test_dspace_fetch_allows_public_host(monkeypatch):
    """Kontrola pozytywna: host publiczny → request DO wykonany (guard nie
    blokuje legalnego pobrania)."""
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("93.184.216.34"))
    get = _benign_get()
    monkeypatch.setattr(network.requests, "get", get)

    # brak dc.title → wynik None, ale request do publicznego hosta jest OK
    assert dspace._fetch_dspace7("https://repo.example.com", UUID) is None
    get.assert_called_once()
