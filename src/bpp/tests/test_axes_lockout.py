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
    """Pin wymaganych wartości polityki: 10 prób, cooloff 1 h, lockout po
    kombinacji (login + IP) — żeby przypadkowa zmiana nie poluzowała ochrony."""
    from django.conf import settings

    assert settings.AXES_FAILURE_LIMIT == 10
    assert settings.AXES_COOLOFF_TIME == timedelta(hours=1)
    assert settings.AXES_LOCKOUT_PARAMETERS == [["username", "ip_address"]]


@override_settings(AXES_ENABLED=True)
@pytest.mark.django_db
def test_lockout_response_renderuje_szablon_bpp(client, django_user_model):
    """Po przekroczeniu limitu użytkownik dostaje pełną stronę BPP z
    komunikatem o blokadzie — a nie gołe ``HttpResponse`` z jednym zdaniem
    (domyślne zachowanie axes, gdy ``AXES_LOCKOUT_TEMPLATE`` jest ``None``)."""
    from django.conf import settings

    django_user_model.objects.create_superuser(
        username=LOCK_USERNAME,
        password=LOCK_PASSWORD,
        email="lock@example.com",
    )

    response = None
    for _ in range(settings.AXES_FAILURE_LIMIT):
        response = _post_login(client, LOCK_USERNAME, "zle-haslo")

    assert response.status_code == 429, (
        "Zablokowane logowanie powinno zwrócić 429 (AXES_HTTP_RESPONSE_CODE)."
    )
    content = response.content.decode("utf-8")
    assert "<html" in content, (
        "Odpowiedź powinna być stroną HTML z szablonu BPP, a nie gołym tekstem "
        "z domyślnego HttpResponse axes."
    )
    assert "Konto tymczasowo zablokowane" in content


@pytest.mark.django_db
def test_akcja_admina_odblokowuje_konto(admin_client, django_user_model):
    """Akcja „Odblokuj konto" na liście użytkowników kasuje wpisy
    ``AccessAttempt`` wybranego użytkownika — i tylko jego."""
    from axes.models import AccessAttempt

    zablokowany = django_user_model.objects.create_user(
        username=LOCK_USERNAME, password=LOCK_PASSWORD
    )
    django_user_model.objects.create_user(username="ktos-inny", password=LOCK_PASSWORD)

    for ip in ("10.0.0.1", "10.0.0.2"):
        AccessAttempt.objects.create(
            username=LOCK_USERNAME,
            ip_address=ip,
            user_agent="pytest",
            http_accept="*/*",
            path_info=ADMIN_LOGIN_URL,
            get_data="",
            post_data="",
            failures_since_start=10,
        )
    AccessAttempt.objects.create(
        username="ktos-inny",
        ip_address="10.0.0.3",
        user_agent="pytest",
        http_accept="*/*",
        path_info=ADMIN_LOGIN_URL,
        get_data="",
        post_data="",
        failures_since_start=10,
    )

    response = admin_client.post(
        "/admin/bpp/bppuser/",
        {
            "action": "odblokuj_logowanie",
            "_selected_action": [str(zablokowany.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200

    assert not AccessAttempt.objects.filter(username=LOCK_USERNAME).exists(), (
        "Akcja powinna skasować wszystkie wpisy AccessAttempt zablokowanego "
        "użytkownika (blokada jest per (login, IP), więc wpisów bywa kilka)."
    )
    assert AccessAttempt.objects.filter(username="ktos-inny").exists(), (
        "Akcja nie powinna ruszać wpisów innych użytkowników."
    )
