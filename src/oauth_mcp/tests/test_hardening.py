import json
from datetime import timedelta

import pytest
from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from model_bakery import baker
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_grant_model,
    set_token_value,
)
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from oauth_mcp.authentication import StrictOAuth2Authentication


def _drf_request(django_request):
    return Request(
        django_request, parsers=[JSONParser(), FormParser(), MultiPartParser()]
    )


# --- transport tokenu: tylko nagłówek Authorization -------------------------


@pytest.mark.django_db
def test_token_w_query_stringu_nie_uwierzytelnia_whoami(access_token, client):
    user, tok = access_token()
    resp = client.get("/api/v1/whoami/", {"access_token": tok.token})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_token_w_query_stringu_na_publicznym_endpoincie_401(access_token, client):
    user, tok = access_token()
    resp = client.get("/api/v1/wydawnictwo_ciagle/", {"access_token": tok.token})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_token_w_naglowku_dalej_dziala(access_token, client):
    user, tok = access_token()
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert resp.status_code == 200


# --- read-only egzekwowane na podstawie request.auth -------------------------


@pytest.mark.django_db
def test_post_z_tokenem_w_body_odrzucony_403(access_token):
    user, tok = access_token()
    factory = APIRequestFactory()
    django_request = factory.post(
        "/api/v1/cokolwiek/",
        {"access_token": tok.token},
        format="multipart",
    )
    request = _drf_request(django_request)
    with pytest.raises(PermissionDenied):
        StrictOAuth2Authentication().authenticate(request)


@pytest.mark.django_db
def test_post_z_tokenem_w_naglowku_odrzucony_403_w_drf(access_token):
    user, tok = access_token()
    factory = APIRequestFactory()
    django_request = factory.post(
        "/inna/sciezka/",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {tok.token}",
    )
    request = _drf_request(django_request)
    with pytest.raises(PermissionDenied):
        StrictOAuth2Authentication().authenticate(request)


@pytest.mark.django_db
def test_get_z_tokenem_w_naglowku_uwierzytelnia(access_token):
    user, tok = access_token()
    factory = APIRequestFactory()
    django_request = factory.get(
        "/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}"
    )
    request = _drf_request(django_request)
    wynik = StrictOAuth2Authentication().authenticate(request)
    assert wynik is not None
    assert wynik[0] == user


@pytest.mark.django_db
def test_query_token_w_authenticate_daje_401(access_token):
    user, tok = access_token()
    factory = APIRequestFactory()
    django_request = factory.get("/api/v1/whoami/", {"access_token": tok.token})
    request = _drf_request(django_request)
    with pytest.raises(AuthenticationFailed):
        StrictOAuth2Authentication().authenticate(request)


# --- middleware: lookup po token_checksum (działa przy hashowaniu) ----------


@pytest.mark.django_db
def test_middleware_blokuje_post_przy_hashowanych_tokenach(client, django_user_model):
    with override_settings(
        OAUTH2_PROVIDER={
            **settings.OAUTH2_PROVIDER,
            "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
        }
    ):
        AccessToken = get_access_token_model()
        Application = get_application_model()
        user = baker.make(django_user_model, is_active=True)
        app = Application.objects.create(
            user=user,
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://claude.ai/callback",
            name="test-mcp",
        )
        tok = AccessToken(
            user=user,
            application=app,
            expires=timezone.now() + timedelta(hours=1),
            scope="read",
        )
        raw = "hashowany-token-abc"
        set_token_value(tok, raw)
        tok.save()
        tok.refresh_from_db()
        assert tok.token == ""  # w bazie nie ma jawnego tokenu

        resp = client.post(
            "/api/v1/raport_slotow_uczelnia/",
            data={},
            HTTP_AUTHORIZATION=f"Bearer {raw}",
            content_type="application/json",
        )
        assert resp.status_code == 403


# --- PKCE: tylko S256 --------------------------------------------------------


def _aplikacja(django_user_model):
    Application = get_application_model()
    user = baker.make(django_user_model, is_active=True)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/cb",
        name="Claude",
    )
    return user, app


@pytest.mark.django_db
def test_pkce_plain_odrzucone(client, django_user_model):
    user, app = _aplikacja(django_user_model)
    client.force_login(user)
    resp = client.post(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "scope": "read",
            "code_challenge": "a" * 64,
            "code_challenge_method": "plain",
            "allow": "Authorize",
        },
    )
    assert "code=" not in resp.get("Location", "")
    assert not get_grant_model().objects.filter(application=app).exists()


@pytest.mark.django_db
def test_pkce_bez_metody_odrzucone(client, django_user_model):
    user, app = _aplikacja(django_user_model)
    client.force_login(user)
    resp = client.post(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "scope": "read",
            "code_challenge": "a" * 64,
            "allow": "Authorize",
        },
    )
    assert "code=" not in resp.get("Location", "")
    assert not get_grant_model().objects.filter(application=app).exists()


@pytest.mark.django_db
def test_pkce_s256_dalej_wydaje_kod(client, django_user_model):
    user, app = _aplikacja(django_user_model)
    client.force_login(user)
    resp = client.post(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "scope": "read",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
            "allow": "Authorize",
        },
    )
    assert resp.status_code == 302
    assert "code=" in resp["Location"]


# --- ekran zgody: host redirect_uri + pochodzenie nazwy ---------------------


@pytest.mark.django_db
def test_ekran_zgody_host_redirect_i_escape_nazwy(client, django_user_model):
    baker.make("bpp.Uczelnia")
    user, app = _aplikacja(django_user_model)
    app.name = "<b>Zaufana</b>"
    app.save()
    client.force_login(user)
    resp = client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
            "scope": "read",
        },
    )
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert "<b>Zaufana</b>" not in tresc
    assert "&lt;b&gt;Zaufana&lt;/b&gt;" in tresc
    assert "<strong>claude.ai</strong>" in tresc
    assert "nazwa pochodzi od aplikacji" in tresc


def test_filtr_host_z_uri():
    from oauth_mcp.templatetags.oauth_mcp_tags import host_z_uri

    assert host_z_uri("https://claude.ai/cb") == "claude.ai"
    assert host_z_uri("http://localhost:3334/cb") == "localhost:3334"
    assert host_z_uri("https://Claude.AI:443/x") == "claude.ai:443"
    assert host_z_uri("") == ""
    assert host_z_uri(None) == ""


# --- DCR: limity redirect_uris ------------------------------------------------


def _dcr(client, redirect_uris):
    return client.post(
        "/o/register/",
        data=json.dumps({"client_name": "Claude", "redirect_uris": redirect_uris}),
        content_type="application/json",
    )


def _uri_o_dlugosci(n):
    prefiks = "https://claude.ai/"
    return prefiks + "a" * (n - len(prefiks))


@pytest.mark.django_db
def test_dcr_za_duzo_redirect_uris_400(client):
    resp = _dcr(client, [f"https://claude.ai/cb{i}" for i in range(6)])
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_redirect_uri"


@pytest.mark.django_db
def test_dcr_za_dlugi_redirect_uri_400(client):
    resp = _dcr(client, [_uri_o_dlugosci(513)])
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_redirect_uri"


@pytest.mark.django_db
def test_dcr_na_granicy_limitow_201(client):
    resp = _dcr(client, [_uri_o_dlugosci(512)[:-1] + str(i) for i in range(5)])
    assert resp.status_code == 201
