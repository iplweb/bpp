import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.http import SimpleCookie


@pytest.fixture
def remove_key():
    key = make_template_fragment_key("google")
    cache.delete(key)


@pytest.mark.django_db
def test_google_analytics_disabled(remove_key, client):
    orig_DEBUG = settings.DEBUG
    orig_GAPID = settings.GOOGLE_ANALYTICS_PROPERTY_ID

    try:
        settings.DEBUG = True
        res = client.get("/")
        assert b"https://www.googletagmanager.com/gtag/js" not in res.content

        settings.DEBUG = False
        settings.GOOGLE_ANALYTICS_PROPERTY_ID = ""
        res = client.get("/")
        assert b"https://www.googletagmanager.com/gtag/js" not in res.content

    finally:
        settings.DEBUG = orig_DEBUG
        settings.GOOGLE_ANALYTICS_PROPERTY_ID = orig_GAPID


@pytest.mark.django_db
def test_google_analytics_enabled(remove_key, client):
    from django.conf import settings

    orig_DEBUG = settings.DEBUG
    orig_GAPID = settings.GOOGLE_ANALYTICS_PROPERTY_ID

    client.cookies = SimpleCookie({"cookielaw_accepted": "1"})

    try:
        settings.DEBUG = False
        settings.GOOGLE_ANALYTICS_PROPERTY_ID = "foobar"

        res = client.get("/")

        assert b"https://www.googletagmanager.com/gtag/js" in res.content

    finally:
        settings.DEBUG = orig_DEBUG
        settings.GOOGLE_ANALYTICS_PROPERTY_ID = orig_GAPID
