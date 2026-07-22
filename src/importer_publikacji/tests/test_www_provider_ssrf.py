"""Testy guardu SSRF providera WWW (uwaga #5 reviewera).

``_validate_url``/``_fetch_page`` nie mogą pozwolić importerowi uderzyć w
adresy loopback/prywatne/link-local (w tym metadata cloud 169.254.169.254),
ani przez bezpośredni URL, ani przez przekierowanie z hosta publicznego.
"""

from unittest.mock import MagicMock

import pytest

from importer_publikacji.providers.www import WWWProvider, network


def _resolve_to(mapping_or_ip):
    """Zbuduj podmiankę ``_resolve_ips``: dict host->[ip] albo jeden ip dla
    każdego hosta."""
    if isinstance(mapping_or_ip, dict):
        return lambda hostname: mapping_or_ip[hostname]
    return lambda hostname: [mapping_or_ip]


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # prywatna 10/8
        "172.16.3.4",  # prywatna 172.16/12
        "192.168.1.10",  # prywatna 192.168/16
        "169.254.169.254",  # metadata cloud (link-local)
        "0.0.0.0",  # unspecified
        "::1",  # loopback v6
        "fd00::1",  # unique-local v6
        "::ffff:127.0.0.1",  # v4-mapped loopback
    ],
)
def test_host_is_safe_blocks_nonpublic(monkeypatch, ip):
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to(ip))
    assert network._host_is_safe("evil.example.com") is False


def test_host_is_safe_allows_public(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("93.184.216.34"))
    assert network._host_is_safe("example.com") is True


def test_host_is_safe_failclosed_on_dns_error(monkeypatch):
    import socket as _socket

    def _boom(hostname):
        raise _socket.gaierror("nxdomain")

    monkeypatch.setattr(network, "_resolve_ips", _boom)
    assert network._host_is_safe("nope.invalid") is False


def test_host_is_safe_blocks_mixed_resolution(monkeypatch):
    # Choćby jeden nie-publiczny adres w wyniku DNS → blokuj (DNS rebinding).
    monkeypatch.setattr(
        network, "_resolve_ips", lambda h: ["93.184.216.34", "127.0.0.1"]
    )
    assert network._host_is_safe("rebind.example.com") is False


def test_validate_url_rejects_internal_host(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("127.0.0.1"))
    assert network._validate_url("http://127.0.0.1/latest/meta-data/") is None


def test_validate_url_accepts_public_host(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("93.184.216.34"))
    assert network._validate_url("https://example.com/a") == "https://example.com/a"


def test_fetch_blocks_direct_internal(monkeypatch):
    """Bezpośredni URL na loopback nie może w ogóle wywołać requests.get."""
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("127.0.0.1"))
    called = MagicMock()
    monkeypatch.setattr(network.requests, "get", called)

    assert network._fetch_page("http://127.0.0.1:8000/") is None
    called.assert_not_called()


def test_fetch_blocks_redirect_to_internal(monkeypatch):
    """Publiczny host przekierowuje na 169.254.169.254 — drugi hop MUSI być
    zablokowany, mimo że pierwszy jest publiczny."""

    def resolve(hostname):
        if hostname == "public.example.com":
            return ["93.184.216.34"]
        return ["169.254.169.254"]

    monkeypatch.setattr(network, "_resolve_ips", resolve)

    redirect = MagicMock()
    redirect.status_code = 302
    redirect.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    get = MagicMock(return_value=redirect)
    monkeypatch.setattr(network.requests, "get", get)

    assert network._fetch_page("https://public.example.com/x") is None
    # Pierwszy (publiczny) hop wywołany, drugi (metadata) już nie.
    assert get.call_count == 1


def test_provider_fetch_rejects_internal_identifier(monkeypatch):
    """Pełna ścieżka providera: identyfikator na 127.0.0.1 → brak wyniku."""
    monkeypatch.setattr(network, "_resolve_ips", _resolve_to("127.0.0.1"))
    get = MagicMock()
    monkeypatch.setattr(network.requests, "get", get)

    assert WWWProvider().fetch("http://127.0.0.1/") is None
    get.assert_not_called()
