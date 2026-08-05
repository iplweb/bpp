"""Testy utwardzenia ``safe_get`` przeciw SSRF (DNS rebinding) i DoS.

Trzy niezależne wektory zamykane tutaj — poza istniejącym guardem hosta
(``test_www_provider_ssrf.py``):

1. **DNS rebinding (TOCTOU)** — walidacja rozwiązuje host raz i widzi adres
   publiczny, ale ``requests``/``urllib3`` rozwiązałby nazwę PONOWNIE przy
   połączeniu. Kontrolowany DNS z niskim TTL mógłby zwrócić publiczny IP przy
   walidacji, a loopback/metadata przy realnym połączeniu. Fix pinuje
   połączenie do zweryfikowanego IP (ten sam zestaw adresów, bez drugiego
   lookupu), zachowując nazwę hosta dla SNI/Host/walidacji certyfikatu.
2. **Nielimitowane ciało** — ``resp.text`` ładował całą odpowiedź do pamięci
   (DoS). Fix streamuje z twardym limitem bajtów.
3. **Brak całkowitego deadline'u** — ``FETCH_TIMEOUT`` był per-hop. Fix nakłada
   budżet czasu na wszystkie hopy łącznie.
"""

import ipaddress
import json
import socket
from unittest.mock import MagicMock

import requests

from importer_publikacji.providers.www import network


def _addrinfo(ip: str, port: int):
    """Zbuduj listę krotek addrinfo dla numerycznego IP (jak realny
    ``getaddrinfo`` dla literału adresu — bez sieciowego DNS)."""
    fam = (
        socket.AF_INET6
        if isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address)
        else socket.AF_INET
    )
    sockaddr = (ip, port) if fam == socket.AF_INET else (ip, port, 0, 0)
    return [(fam, socket.SOCK_STREAM, 6, "", sockaddr)]


class _FakeResp:
    """Minimalna namiastka ``requests.Response`` w trybie ``stream=True``."""

    def __init__(self, *, status_code=200, headers=None, chunks=()):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = list(chunks)
        self.closed = False
        self._content = None

    def iter_content(self, chunk_size=1):
        yield from self._chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def close(self):
        self.closed = True

    @property
    def text(self):
        return (self._content or b"").decode("utf-8", "replace")

    def json(self):
        return json.loads(self._content or b"null")


# --- 1. DNS rebinding -----------------------------------------------------


def test_pin_host_overrides_system_resolution():
    """W obrębie ``_pin_host`` wrapper ``socket.getaddrinfo`` zwraca pinowany
    adres nawet gdyby systemowy resolver zwrócił coś innego (rebinding)."""
    with network._pin_host("evil.example.com", ["93.184.216.34"]):
        infos = socket.getaddrinfo("evil.example.com", 443)
    assert infos[0][4][0] == "93.184.216.34"
    # Poza kontekstem pin znika (nie przecieka na inne wywołania).
    assert getattr(network._pin, "hosts", None) in (None, {})


def test_safe_get_pins_connection_to_validated_ip(monkeypatch):
    """Walidacja widzi publiczny IP; systemowy resolver (użyty przy realnym
    połączeniu) udaje rebinding na loopback. ``safe_get`` MUSI połączyć się z
    zweryfikowanym IP, nie z podmienionym."""
    host = "rebind.example.com"
    validated = "93.184.216.34"

    monkeypatch.setattr(network, "_resolve_ips", lambda h: [validated])

    def _rebinding_system(h, *a, **k):
        port = a[0] if a else 0
        try:
            ipaddress.ip_address(h)  # literał IP → zwróć bez zmian
            return _addrinfo(h, port or 0)
        except ValueError:
            return _addrinfo("127.0.0.1", port or 0)  # nazwa → rebinding

    monkeypatch.setattr(network, "_system_getaddrinfo", _rebinding_system)

    captured = {}

    def fake_get(url, **kwargs):
        # Symuluj to, co urllib3 robi przy connect: rozwiąż host przez
        # (owinięty) socket.getaddrinfo i zapamiętaj docelowy adres.
        infos = socket.getaddrinfo("rebind.example.com", 443)
        captured["ip"] = infos[0][4][0]
        return _FakeResp(chunks=[b"<html><title>ok</title></html>"])

    monkeypatch.setattr(network.requests, "get", fake_get)

    network.safe_get(f"https://{host}/x")
    assert captured["ip"] == validated  # pinowane, NIE 127.0.0.1


# --- 2. Twardy limit rozmiaru ciała --------------------------------------


def test_safe_get_aborts_on_oversized_body(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", lambda h: ["93.184.216.34"])
    monkeypatch.setattr(network, "MAX_RESPONSE_BYTES", 50)

    resp = _FakeResp(chunks=[b"x" * 30, b"x" * 30])  # 60 B > 50 B
    monkeypatch.setattr(network.requests, "get", lambda *a, **k: resp)

    assert network.safe_get("https://example.com/big") is None
    assert resp.closed


def test_safe_get_aborts_on_declared_oversized_content_length(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", lambda h: ["93.184.216.34"])
    monkeypatch.setattr(network, "MAX_RESPONSE_BYTES", 50)

    resp = _FakeResp(
        headers={"Content-Length": "1000000"},
        chunks=[b"x"],  # nie powinno być nawet czytane
    )
    monkeypatch.setattr(network.requests, "get", lambda *a, **k: resp)

    assert network.safe_get("https://example.com/big") is None
    assert resp.closed


# --- 3. Całkowity deadline ------------------------------------------------


def test_safe_get_enforces_total_deadline(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", lambda h: ["93.184.216.34"])
    monkeypatch.setattr(network, "TOTAL_DEADLINE", 0)  # budżet z góry wyczerpany

    get = MagicMock(return_value=_FakeResp(chunks=[b"ok"]))
    monkeypatch.setattr(network.requests, "get", get)

    assert network.safe_get("https://example.com/") is None
    get.assert_not_called()


# --- Regresja: legalne pobranie nadal działa ------------------------------


def test_safe_get_returns_capped_body_for_public_host(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", lambda h: ["93.184.216.34"])

    body = b"<html><head><title>ok</title></head><body>hej</body></html>"
    resp = _FakeResp(chunks=[body[:10], body[10:]])
    monkeypatch.setattr(network.requests, "get", lambda *a, **k: resp)

    got = network.safe_get("https://example.com/ok")
    assert got is resp
    assert got._content == body
    assert got.text == body.decode("utf-8")
    assert not resp.closed
