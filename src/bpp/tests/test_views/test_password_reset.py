import pytest
from django.apps import apps
from django.core import mail
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.skipif(
    apps.is_installed("microsoft_auth"), reason="działa bez django_microsoft_auth"
)
def test_password_reset(webtest_app, normal_django_user):
    EMAIL = "foo@bar.pl"
    normal_django_user.email = EMAIL
    normal_django_user.save()

    url = reverse("password_reset")
    page = webtest_app.get(url)  # noqa
    page.forms[0]["email"] = EMAIL
    page = page.forms[0].submit().maybe_follow()

    assert page.status_code == 200
    assert len(mail.outbox) == 1


@pytest.mark.django_db
@pytest.mark.skipif(
    apps.is_installed("microsoft_auth"), reason="działa bez django_microsoft_auth"
)
def test_password_reset_rate_limited(client, settings):
    # M5: nadmiarowe żądania resetu (email-bombing) muszą być ograniczane
    # per-IP. test.py ma DummyCache (no-op) → wymuszamy realny licznik.
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    from django.core.cache import cache

    cache.clear()

    url = reverse("password_reset")
    for _ in range(5):
        assert client.post(url, {"email": "spam@example.com"}).status_code != 429
    # Kolejne żądanie z tego samego IP jest odrzucane (429).
    assert client.post(url, {"email": "spam@example.com"}).status_code == 429


def _locmem(settings):
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    from django.core.cache import cache

    cache.clear()


def _post_z_ip(client, url, email, ip):
    return client.post(url, {"email": email}, REMOTE_ADDR=ip)


@pytest.mark.django_db
@pytest.mark.skipif(
    apps.is_installed("microsoft_auth"), reason="działa bez django_microsoft_auth"
)
def test_password_reset_limit_per_email(client, settings, normal_django_user):
    _locmem(settings)
    normal_django_user.email = "limit@example.com"
    normal_django_user.save()

    url = reverse("password_reset")
    odpowiedzi = [
        # Różne IP — limit per-IP nie może tu zadziałać.
        _post_z_ip(client, url, " Limit@Example.com ", f"10.0.0.{i}")
        for i in range(1, 6)
    ]

    assert len(mail.outbox) == 3
    # Odpowiedź po przekroczeniu limitu e-maila jest taka sama jak zwykła.
    for res in odpowiedzi:
        assert res.status_code == odpowiedzi[0].status_code == 302
        assert res["Location"] == odpowiedzi[0]["Location"]


@pytest.mark.django_db
@pytest.mark.skipif(
    apps.is_installed("microsoft_auth"), reason="działa bez django_microsoft_auth"
)
def test_password_reset_limit_per_email_nie_zdradza_istnienia_konta(
    client, settings, normal_django_user
):
    _locmem(settings)
    normal_django_user.email = "istnieje@example.com"
    normal_django_user.save()

    url = reverse("password_reset")
    istniejacy = [
        _post_z_ip(client, url, "istnieje@example.com", f"10.0.1.{i}")
        for i in range(1, 5)
    ]
    nieistniejacy = [
        _post_z_ip(client, url, "brak-konta@example.com", f"10.0.2.{i}")
        for i in range(1, 5)
    ]
    for a, b in zip(istniejacy, nieistniejacy, strict=True):
        assert a.status_code == b.status_code
        assert a.get("Location") == b.get("Location")


def test_password_reset_licznik_atomowy_add_incr(settings):
    from django_bpp.views import RateLimitedPasswordResetFormView as V

    _locmem(settings)
    wyniki = [V._zuzyj_limit("pwreset-test", 2) for _ in range(4)]
    assert wyniki == [True, True, False, False]


def test_password_reset_licznik_pod_dummycache_jest_noop(settings):
    from django_bpp.views import RateLimitedPasswordResetFormView as V

    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
    }
    assert all(V._zuzyj_limit("pwreset-test", 1) for _ in range(3))
