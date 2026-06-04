"""Testy ochrony przed zgadywaniem hasła (brute-force) — django-axes.

W ``settings/test.py`` axes jest domyślnie WYŁĄCZONE (``AXES_ENABLED = False``),
bo ``Client.login()`` woła ``authenticate()`` bez ``request`` i axes podniósłby
wtedy ``AxesBackendRequestParameterRequired``, wywracając fixture'y logowania.
Dlatego każdy test, który faktycznie sprawdza lockout, MUSI jawnie włączyć axes
przez ``@override_settings(AXES_ENABLED=True)``.
"""

from datetime import timedelta

import pytest
from django.test.utils import override_settings

ADMIN_LOGIN_URL = "/admin/login/"
LOCK_USERNAME = "axes-locktest"
LOCK_PASSWORD = "correct-horse-battery-staple"


def _post_login(client, username, password):
    return client.post(
        ADMIN_LOGIN_URL,
        {"username": username, "password": password, "next": "/admin/"},
    )


@override_settings(AXES_ENABLED=True)
@pytest.mark.django_db
def test_account_ip_locked_out_after_failure_limit(client, django_user_model):
    """Po AXES_FAILURE_LIMIT nieudanych próbach para (login, IP) jest
    zablokowana — nawet POPRAWNE hasło nie loguje."""
    django_user_model.objects.create_superuser(
        username=LOCK_USERNAME,
        password=LOCK_PASSWORD,
        email="lock@example.com",
    )
    from django.conf import settings

    for _ in range(settings.AXES_FAILURE_LIMIT):
        _post_login(client, LOCK_USERNAME, "zle-haslo")

    # Sanity: dopóki nie weszło axes, ta sama (login, IP) wciąż loguje
    # poprawnym hasłem. Po przekroczeniu limitu — NIE.
    _post_login(client, LOCK_USERNAME, LOCK_PASSWORD)
    assert "_auth_user_id" not in client.session, (
        "Konto powinno być zablokowane po przekroczeniu limitu nieudanych prób, "
        "ale poprawne hasło i tak zalogowało użytkownika."
    )


@override_settings(AXES_ENABLED=True)
@pytest.mark.django_db
def test_successful_login_works_under_axes(client, django_user_model):
    """Z włączonym axes normalne logowanie poprawnym hasłem nadal działa
    (axes nie wywraca realnego widoku logowania, który przekazuje request)."""
    django_user_model.objects.create_superuser(
        username=LOCK_USERNAME,
        password=LOCK_PASSWORD,
        email="lock@example.com",
    )
    _post_login(client, LOCK_USERNAME, LOCK_PASSWORD)
    assert "_auth_user_id" in client.session, (
        "Poprawne hasło poniżej limitu prób powinno zalogować użytkownika."
    )


def test_axes_configured_with_required_policy():
    """Pin wymaganych wartości polityki: 10 prób, cooloff 30 min, lockout po
    kombinacji (login + IP) — żeby przypadkowa zmiana nie poluzowała ochrony."""
    from django.conf import settings

    assert settings.AXES_FAILURE_LIMIT == 10
    assert settings.AXES_COOLOFF_TIME == timedelta(minutes=30)
    assert settings.AXES_LOCKOUT_PARAMETERS == [["username", "ip_address"]]
