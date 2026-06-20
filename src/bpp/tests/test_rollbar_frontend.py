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
