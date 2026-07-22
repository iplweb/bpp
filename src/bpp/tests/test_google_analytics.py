import pytest
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.http import SimpleCookie


@pytest.fixture
def remove_key():
    # Czyscimy cache fragmentu "google" przed ORAZ po tescie — inaczej
    # nagrzany (zacache'owany) fragment wyciekłby na innego testu na tym
    # samym workerze xdist i zaburzył jego wynik.
    key = make_template_fragment_key("google")
    cache.delete(key)
    yield
    cache.delete(key)


@pytest.mark.django_db
def test_google_analytics_disabled(remove_key, client, settings):
    settings.DEBUG = True
    res = client.get("/")
    assert b"https://www.googletagmanager.com/gtag/js" not in res.content

    settings.DEBUG = False
    settings.GOOGLE_ANALYTICS_PROPERTY_ID = ""
    res = client.get("/")
    assert b"https://www.googletagmanager.com/gtag/js" not in res.content


@pytest.mark.django_db
def test_google_analytics_enabled(remove_key, client, settings):
    client.cookies = SimpleCookie({"cookielaw_accepted": "1"})

    settings.DEBUG = False
    settings.GOOGLE_ANALYTICS_PROPERTY_ID = "foobar"

    res = client.get("/")

    assert b"https://www.googletagmanager.com/gtag/js" in res.content
