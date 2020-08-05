import threading
import warnings, os

import pytest
from channels.testing import ChannelsLiveServerTestCase
from daphne.testing import DaphneProcess

from pytest_django.lazy_django import skip_if_no_django
from pytest_django.plugin import _blocking_manager

from asgi_testing import DaphneThread
from bpp.models import Rekord

from pytest_django.compat import setup_databases, teardown_databases



class PytestChannelsLiveServerTestCase(ChannelsLiveServerTestCase):
    ProtocolServerProcess = DaphneThread
    @property
    def url(self):
        return self.live_server_url

@pytest.fixture(scope="session")
def asgi_live_server(request):
    """Run a live Django server in the background during tests

    The address the server is started from is taken from the
    --liveserver command line option or if this is not provided from
    the DJANGO_LIVE_TEST_SERVER_ADDRESS environment variable.  If
    neither is provided ``localhost:8081,8100-8200`` is used.  See the
    Django documentation for its full syntax.

    NOTE: If the live server needs database access to handle a request
          your test will have to request database access.  Furthermore
          when the tests want to see data added by the live-server (or
          the other way around) transactional database access will be
          needed as data inside a transaction is not shared between
          the live server and test code.

          Static assets will be automatically served when
          ``django.contrib.staticfiles`` is available in INSTALLED_APPS.
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

#
# @pytest.fixture(autouse=True, scope="function")
# def _asgi_live_server_helper(request):
#     """Helper to make asgi_live_server work, internal to pytest-django.
#
#     This helper will dynamically request the transactional_db fixture
#     for a test which uses the live_server fixture.  This allows the
#     server and test to access the database without having to mark
#     this explicitly which is handy since it is usually required and
#     matches the Django behaviour.
#
#     The separate helper is required since live_server can not request
#     transactional_db directly since it is session scoped instead of
#     function-scoped.
#
#     It will also override settings only for the duration of the test.
#     """
#     if "asgi_live_server" not in request.fixturenames:
#         return
#
#     request.getfixturevalue("transactional_db")
#
#     asgi_live_server = request.getfixturevalue("asgi_live_server")
#     asgi_live_server._asgi_live_server_modified_settings.enable()
#     request.addfinalizer(asgi_live_server._asgi_live_server_modified_settings.disable)
