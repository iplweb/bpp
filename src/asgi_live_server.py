import os
import warnings

import pytest
from asgiref.sync import sync_to_async
from pytest_django.lazy_django import skip_if_no_django

# https://github.com/django/channels/issues/1722#issuecomment-1032965993


def patch_sync_to_async(*args, **kwargs):
    """
    Monkey Patch the sync_to_async decorator
    ---------------------------------------
    ASGIRef made a change in their defaults that has caused major problems
    for channels. The decorator below needs to be updated to use
    thread_sensitive=False, thats why we are patching it on our side for now.
    https://github.com/django/channels/blob/main/channels/http.py#L220
    """
    kwargs["thread_sensitive"] = False
    return sync_to_async(*args, **kwargs)


@pytest.fixture(scope="session")
def asgi_live_server(request):
    """Run a live Daphne server in the background during tests."""
    skip_if_no_django()

    import asgiref

    # Monkey Patches
    asgiref.sync.sync_to_async = patch_sync_to_async

    from channels.testing import ChannelsLiveServerTestCase

    from asgi_testing import DaphneThread

    class PytestChannelsLiveServerTestCase(ChannelsLiveServerTestCase):
        ProtocolServerProcess = DaphneThread

        @property
        def url(self):
            return self.live_server_url

    import django

    addr = request.config.getvalue("liveserver") or os.getenv(
        "DJANGO_LIVE_TEST_SERVER_ADDRESS"
    )

    if addr and ":" in addr:
        if django.VERSION >= (1, 11):
            ports = addr.split(":")[1]
            if "-" in ports or "," in ports:
                warnings.warn(
                    "Specifying multiple live server ports is not supported "
                    "in Django 1.11. This will be an error in a future "
                    "pytest-django release."
                )

    if not addr:
        if django.VERSION < (1, 11):
            addr = "localhost:8081,8100-8200"
        else:
            addr = "localhost"

    server = PytestChannelsLiveServerTestCase(methodName="__init__")
    server._pre_setup()

    request.addfinalizer(server._post_teardown)

    return server
