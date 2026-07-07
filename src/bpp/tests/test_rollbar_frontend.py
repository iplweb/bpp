import pytest
from django.conf import settings
from django.test import RequestFactory, override_settings

from bpp.context_processors.rollbar import rollbar_client


def test_rollbar_client_no_token_returns_empty():
    request = RequestFactory().get("/")
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN=""):
        assert rollbar_client(request) == {}


def test_rollbar_client_with_token_returns_config():
    request = RequestFactory().get("/")
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        ctx = rollbar_client(request)
    client = ctx["ROLLBAR_CLIENT"]
    assert client["accessToken"] == "post_client_abc"
    assert client["environment"] == settings.ROLLBAR["environment"]
    assert client["codeVersion"] == str(settings.ROLLBAR["code_version"])


@pytest.mark.django_db
def test_rollbar_snippet_absent_without_token(client):
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN=""):
        res = client.get("/")
    assert b"_rollbarConfig" not in res.content


@pytest.mark.django_db
def test_rollbar_snippet_present_with_token(client):
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        res = client.get("/")
    assert b"_rollbarConfig" in res.content
    assert b"post_client_abc" in res.content
    assert b"rollbar/rollbar.umd.min" in res.content


@pytest.mark.django_db
def test_rollbar_snippet_has_no_person_data(client):
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        res = client.get("/")
    assert b"_rollbarConfig" in res.content
    assert b"person:" not in res.content


@pytest.mark.django_db
def test_rollbar_code_version_matches_VERSION(client):
    from django_bpp.version import VERSION

    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        res = client.get("/")
    assert VERSION.encode() in res.content
