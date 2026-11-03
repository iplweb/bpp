"""Importer pobiera dane z adresów użytkownika wyłącznie przez HTTPS (443).

Dotyczy wspólnego klienta ``safe_get`` (WWW, DSpace, Omega-PSIR) oraz
walidacji URL wejściowego: ``http://`` bez portu (albo z ``:80``) jest
przepisywany na ``https://``; każdy inny schemat/port jest odrzucany, także
na każdym hopie przekierowania.
"""

from unittest.mock import MagicMock

import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportSession
from importer_publikacji.providers import dspace
from importer_publikacji.providers.www import WWWProvider, network

UUID = "00000000-0000-0000-0000-000000000000"
PUBLIC_IP = "93.184.216.34"


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(network, "_resolve_ips", lambda h: [PUBLIC_IP])


def _ok_resp(body=b"<html><title>ok</title></html>"):
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.iter_content = lambda chunk_size=1: iter([body])
    return resp


def _redirect(location):
    resp = MagicMock()
    resp.status_code = 302
    resp.headers = {"Location": location}
    return resp


# --- normalizacja URL wejściowego -----------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/a", "https://example.com/a"),
        ("https://example.com:443/a", "https://example.com:443/a"),
        ("http://example.com/a?x=1", "https://example.com/a?x=1"),
        ("http://example.com:80/a", "https://example.com/a"),
        ("HTTP://example.com/a", "https://example.com/a"),
        ("http://[2001:db8::1]/a", "https://[2001:db8::1]/a"),
    ],
)
def test_https_only_accepts_and_upgrades(url, expected):
    assert network._https_only(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:8443/",
        "http://example.com:8080/",
        "http://example.com:443/",
        "https://example.com:80/",
        "https://example.com:abc/",
        "https://example.com:99999/",
        "ftp://example.com/",
        "file:///etc/hosts",
    ],
)
def test_https_only_rejects_other_schemes_and_ports(url):
    assert network._https_only(url) is None


def test_validate_url_upgrades_http(public_dns):
    assert network._validate_url("http://example.com/x") == "https://example.com/x"


@pytest.mark.parametrize(
    "url", ["https://example.com:8443/", "http://example.com:8080/"]
)
def test_validate_url_rejects_non_443_port(public_dns, url):
    assert network._validate_url(url) is None


def test_url_transport_error_message():
    msg = network.url_transport_error("https://example.com:8443/")
    assert msg is not None
    assert "HTTPS" in msg and "443" in msg
    assert network.url_transport_error("http://example.com/") is None
    assert network.url_transport_error("https://example.com/") is None


# --- safe_get: każdy hop https:443 ----------------------------------------


def test_safe_get_https_works(public_dns, monkeypatch):
    get = MagicMock(return_value=_ok_resp())
    monkeypatch.setattr(network.requests, "get", get)

    resp = network.safe_get("https://example.com/x")
    assert resp is not None
    assert get.call_args[0][0] == "https://example.com/x"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/x",
        "https://example.com:8443/x",
        "http://example.com:8080/x",
    ],
)
def test_safe_get_refuses_non_https_443(public_dns, monkeypatch, url):
    get = MagicMock(return_value=_ok_resp())
    monkeypatch.setattr(network.requests, "get", get)

    assert network.safe_get(url) is None
    get.assert_not_called()


@pytest.mark.parametrize(
    "location",
    [
        "http://example.com/y",
        "https://example.com:8443/y",
        "//example.com:8080/y",
        "https://example.com:99999/y",
    ],
)
def test_safe_get_refuses_redirect_off_https_443(public_dns, monkeypatch, location):
    get = MagicMock(side_effect=[_redirect(location), _ok_resp()])
    monkeypatch.setattr(network.requests, "get", get)

    assert network.safe_get("https://example.com/x") is None
    assert get.call_count == 1


def test_safe_get_follows_https_redirect(public_dns, monkeypatch):
    get = MagicMock(side_effect=[_redirect("https://other.example.com/y"), _ok_resp()])
    monkeypatch.setattr(network.requests, "get", get)

    assert network.safe_get("https://example.com/x") is not None
    assert get.call_args[0][0] == "https://other.example.com/y"


# --- providery --------------------------------------------------------------


def test_www_provider_fetch_upgrades_http(public_dns, monkeypatch):
    from importer_publikacji.providers.www import provider as www_provider

    fetch_page = MagicMock(return_value=None)
    monkeypatch.setattr(www_provider, "_fetch_page", fetch_page)

    WWWProvider().fetch("http://example.com/art")
    fetch_page.assert_called_once_with("https://example.com/art")


def test_dspace_validate_identifier_upgrades_http():
    provider = dspace.DSpaceProvider()
    assert (
        provider.validate_identifier(f"http://repo.example.com/items/{UUID}")
        == f"https://repo.example.com/items/{UUID}"
    )
    assert (
        provider.validate_identifier("http://repo.example.com/handle/1/2")
        == "https://repo.example.com/handle/1/2"
    )


def test_dspace_validate_identifier_rejects_port():
    provider = dspace.DSpaceProvider()
    url = f"https://repo.example.com:8443/items/{UUID}"
    assert provider.validate_identifier(url) is None
    assert "443" in provider.identifier_error(url)


def test_dspace_fetch_upgrades_http(public_dns, monkeypatch):
    get = MagicMock(return_value=_ok_resp(b'{"metadata": []}'))
    monkeypatch.setattr(network.requests, "get", get)
    monkeypatch.setattr(dspace, "_fallback_to_www", lambda identifier: None)

    dspace.DSpaceProvider().fetch(f"http://repo.example.com/items/{UUID}")
    assert get.call_args_list[0][0][0].startswith("https://repo.example.com/")


# --- widok kreatora: czytelny komunikat -----------------------------------


@pytest.mark.django_db
def test_fetch_view_shows_https_only_message(client, django_user_model):
    user = baker.make(django_user_model, is_staff=True, is_superuser=True)
    client.force_login(user)

    response = client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "Pozostałe strony WWW", "identifier": "https://a.pl:8443/"},
    )

    assert response.status_code == 200
    assert "wyłącznie przez HTTPS" in response.content.decode()
    assert ImportSession.objects.count() == 0
