"""Testy guardu SSRF providera Omega-PSIR (M1).

``_fetch_omega_psir_jsonld`` pobierał JSON-LD z hosta wyprowadzonego z URL-a
użytkownika z domyślnym ``allow_redirects=True`` i bez rewalidacji hosta —
publiczny host Omega-PSIR mógł przekierować na adres wewnętrzny
(np. 169.254.169.254), omijając guard SSRF walidowany tylko w ``_validate_url``.
Teraz fetch idzie przez wspólny ``safe_get`` (walidacja hosta + per-hop
śledzenie redirectów).
"""

from unittest.mock import MagicMock

import pytest

from importer_publikacji.providers.www import network, omega_psir

# identyfikator artykułu Omega-PSIR: [A-Za-z]{2,5}[0-9a-f]{32}
IDENT = "abc" + "0" * 32


def _resolve_to(ip):
    return lambda hostname: [ip]


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # prywatna 10/8
        "169.254.169.254",  # metadata cloud (link-local)
        "::1",  # loopback v6
    ],
)
def test_omega_psir_fetch_blocks_internal_host(monkeypatch, ip):
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to(ip))
    get = MagicMock()
    monkeypatch.setattr(network.requests, "get", get)

    assert omega_psir._fetch_omega_psir_jsonld("http://repo.internal", IDENT) is None
    get.assert_not_called()


def test_omega_psir_fetch_allows_public_host(monkeypatch):
    """Kontrola pozytywna: host publiczny → request DO wykonany."""
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("93.184.216.34"))
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.json.return_value = []
    resp.iter_content = lambda chunk_size=1: iter([b"[]"])
    get = MagicMock(return_value=resp)
    monkeypatch.setattr(network.requests, "get", get)

    assert omega_psir._fetch_omega_psir_jsonld("https://repo.example.com", IDENT) == []
    get.assert_called_once()
