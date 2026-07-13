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
