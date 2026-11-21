"""Odmowa logowania OIDC musi być widoczna dla użytkownika.

``mozilla_django_oidc`` łapie ``SuspiciousOperation`` z backendu i robi
cichy redirect na ``LOGIN_REDIRECT_URL_FAILURE`` (``/``). Test przechodzi
cały prawdziwy callback (``/oidc/callback/``) z zaślepionym ruchem do IdP,
podąża za redirectem i sprawdza, że powód odmowy pokazuje się na stronie
docelowej dokładnie raz (i znika przy następnej odsłonie).
"""

import importlib

import pytest
from django.contrib import messages
from django.urls import clear_url_caches, reverse
from django.utils.html import escapejs
from model_bakery import baker

from oidc_integration.backends import BppOIDCBackend

ISSUER = "https://sso.uczelnia.example.org/realms/uczelnia"
BACKEND = "oidc_integration.backends.BppOIDCBackend"


@pytest.fixture
def oidc_callback(settings, monkeypatch):
    import django_bpp.urls

    settings.OIDC_LOGIN_ENABLED = True
    settings.OIDC_OP_ISSUER = ISSUER
    settings.OIDC_RP_CLIENT_ID = "bpp"
    settings.OIDC_RP_CLIENT_SECRET = "secret"
    settings.OIDC_OP_AUTHORIZATION_ENDPOINT = ISSUER + "/auth"
    settings.OIDC_OP_TOKEN_ENDPOINT = ISSUER + "/token"
    settings.OIDC_OP_USER_ENDPOINT = ISSUER + "/userinfo"
    settings.OIDC_OP_JWKS_ENDPOINT = ISSUER + "/certs"
    settings.OIDC_RP_SIGN_ALGO = "RS256"
    settings.OIDC_REQUIRE_EMAIL_VERIFIED = True
    if BACKEND not in settings.AUTHENTICATION_BACKENDS:
        settings.AUTHENTICATION_BACKENDS = [
            *settings.AUTHENTICATION_BACKENDS,
            BACKEND,
        ]

    # Zero ruchu sieciowego: token i jego weryfikacja zaślepione; userinfo
    # przechodzi przez prawdziwą normalizację backendu.
    payload = {
        "iss": ISSUER,
        "sub": "sub-123",
        "aud": "bpp",
        "email_verified": True,
    }
    monkeypatch.setattr(
        BppOIDCBackend,
        "get_token",
        lambda self, token_payload: {"id_token": "it", "access_token": "at"},
    )
    monkeypatch.setattr(
        BppOIDCBackend, "verify_token", lambda self, token, **kw: dict(payload)
    )
    monkeypatch.setattr(
        BppOIDCBackend,
        "get_userinfo",
        lambda self, at, it, p: self._normalized(
            {
                **payload,
                "email": "jan.kowalski@uczelnia.example.org",
                "preferred_username": "jkowalski",
            }
        ),
    )

    importlib.reload(django_bpp.urls)
    clear_url_caches()
    yield
    settings.OIDC_LOGIN_ENABLED = False
    importlib.reload(django_bpp.urls)
    clear_url_caches()


def _start_callback(client):
    session = client.session
    session["oidc_states"] = {"st": {"nonce": "n", "code_verifier": None}}
    session.save()
    return client.get(
        reverse("oidc_authentication_callback"),
        {"code": "c", "state": "st"},
        follow=True,
    )


@pytest.mark.django_db
def test_odmowa_oidc_pokazuje_komunikat_raz(client, uczelnia, oidc_callback):
    # Konto z tym adresem już istnieje i nie jest związane z SSO → fail-closed.
    baker.make("bpp.BppUser", email="jan.kowalski@uczelnia.example.org")

    resp = _start_callback(client)

    assert resp.redirect_chain, "callback powinien przekierować"
    assert resp.status_code == 200
    assert not resp.wsgi_request.user.is_authenticated

    shown = [m for m in resp.context["messages"] if m.level == messages.ERROR]
    assert len(shown) == 1
    text = shown[0].message
    assert "konto z tym adresem już istnieje" in text
    assert escapejs(text) in resp.content.decode()

    # Flash-once: kolejna odsłona nie pokazuje komunikatu ponownie.
    again = client.get("/")
    assert escapejs(text) not in again.content.decode()
