import os
import warnings

import pytest
from channels.testing import ChannelsLiveServerTestCase
from pytest_django.lazy_django import skip_if_no_django

from asgi_testing import DaphneThread


class PytestChannelsLiveServerTestCase(ChannelsLiveServerTestCase):
    ProtocolServerProcess = DaphneThread

    @property
    def url(self):
        return self.live_server_url


@pytest.fixture(scope="session")
def asgi_live_server(request):
    """Run a live Daphne server in the background during tests.
    """
    skip_if_no_django()

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
