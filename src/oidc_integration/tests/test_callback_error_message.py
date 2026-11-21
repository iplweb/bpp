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
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from oidc_integration import backends as oidc_backends
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

    # Zero ruchu sieciowego: token, jego weryfikacja i odpowiedź userinfo
    # zaślepione; claimy przechodzą przez PRAWDZIWE ``get_userinfo`` backendu
    # (scalenie z payloadem + normalizacja e-maila). Test może nadpisać
    # ``state["payload"]`` / ``state["userinfo"]``.
    state = {
        "payload": {
            "iss": ISSUER,
            "sub": "sub-123",
            "aud": "bpp",
            "email_verified": True,
        },
        "userinfo": {
            "sub": "sub-123",
            "email": "jan.kowalski@uczelnia.example.org",
            "preferred_username": "jkowalski",
        },
    }
    monkeypatch.setattr(
        BppOIDCBackend,
        "get_token",
        lambda self, token_payload: {"id_token": "it", "access_token": "at"},
    )
    monkeypatch.setattr(
        BppOIDCBackend,
        "verify_token",
        lambda self, token, **kw: dict(state["payload"]),
    )
    # Bazowe (mozilla) ``get_userinfo`` robi GET na userinfo endpoint —
    # zaślepiamy tylko je, nadpisanie w ``BppOIDCBackend`` działa naprawdę.
    monkeypatch.setattr(
        OIDCAuthenticationBackend,
        "get_userinfo",
        lambda self, at, it, p: dict(state["userinfo"]),
    )

    importlib.reload(django_bpp.urls)
    clear_url_caches()
    yield state
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


def _assert_shown_once(client, resp, expected):
    assert resp.redirect_chain, "callback powinien przekierować"
    assert resp.status_code == 200
    assert not resp.wsgi_request.user.is_authenticated

    shown = [m for m in resp.context["messages"] if m.level == messages.ERROR]
    assert [m.message for m in shown] == [expected]
    assert escapejs(expected) in resp.content.decode()
    # Komunikat dla użytkownika — bez technicznego żargonu.
    assert "OIDC" not in expected

    # Flash-once: kolejna odsłona nie pokazuje komunikatu ponownie.
    again = client.get("/")
    assert escapejs(expected) not in again.content.decode()


@pytest.mark.django_db
def test_odmowa_oidc_pokazuje_komunikat_raz(client, uczelnia, oidc_callback):
    # Konto z tym adresem już istnieje i nie jest związane z SSO → fail-closed.
    baker.make("bpp.BppUser", email="jan.kowalski@uczelnia.example.org")

    resp = _start_callback(client)

    _assert_shown_once(client, resp, oidc_backends.MSG_KONTO_ISTNIEJE)


@pytest.mark.django_db
def test_odmowa_oidc_niepotwierdzony_email(client, uczelnia, oidc_callback):
    oidc_callback["payload"]["email_verified"] = False

    resp = _start_callback(client)

    _assert_shown_once(client, resp, oidc_backends.MSG_EMAIL_NIEPOTWIERDZONY)


@pytest.mark.django_db
def test_odmowa_oidc_brak_emaila(client, uczelnia, oidc_callback):
    oidc_callback["userinfo"] = {"sub": "sub-123", "preferred_username": "jk"}

    resp = _start_callback(client)

    _assert_shown_once(client, resp, oidc_backends.MSG_BRAK_EMAILA)


@pytest.mark.django_db
def test_odmowa_oidc_konto_nieaktywne(client, uczelnia, oidc_callback):
    from oidc_integration.models import OIDCIdentity

    u = baker.make(
        "bpp.BppUser",
        email="jan.kowalski@uczelnia.example.org",
        is_active=False,
    )
    OIDCIdentity.objects.create(user=u, issuer=ISSUER, sub="sub-123")

    resp = _start_callback(client)

    _assert_shown_once(client, resp, oidc_backends.MSG_KONTO_NIEAKTYWNE)


@pytest.mark.django_db
def test_odmowa_oidc_jedyne_konto_z_adresem_nieaktywne(client, uczelnia, oidc_callback):
    # Konto z adresem istnieje, ale jest nieaktywne — nie każemy logować się
    # hasłem (i tak by nie zadziałało), tylko mówimy, że jest nieaktywne.
    baker.make(
        "bpp.BppUser",
        email="jan.kowalski@uczelnia.example.org",
        is_active=False,
    )

    resp = _start_callback(client)

    _assert_shown_once(client, resp, oidc_backends.MSG_KONTO_NIEAKTYWNE)
