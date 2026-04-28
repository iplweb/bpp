import pytest
from django.db import DEFAULT_DB_ALIAS

# Fix for VCR.py compatibility with urllib3
# This resolves the AttributeError: 'VCRHTTPConnection' has no attribute 'debuglevel'


def set_database_connection():
    import os

    from django.conf import settings
    from django.db import connections

    test_db_name = connections[DEFAULT_DB_ALIAS].settings_dict["NAME"]

    if not test_db_name.startswith("test_"):
        test_db_name = f"test_{test_db_name}"

    if os.environ.get("PYTEST_XDIST_WORKER", "master").startswith("gw"):
        if not test_db_name.endswith("_" + os.environ["PYTEST_XDIST_WORKER"]):
            test_db_name += "_" + os.environ.get("PYTEST_XDIST_WORKER")

    settings.DATABASES["default"]["NAME"] = test_db_name

    # Pomoże?
    settings.CELERY_ALWAYS_EAGER = True

    settings.TESTING = True


class _ChannelsLiveServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._port = port  # For backward compatibility

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

    @property
    def live_server_url(self):
        return self.url

    @property
    def live_server_ws_url(self):
        return f"ws://{self.host}:{self.port}"


def _spawn_daphne():
    """Start a Daphne process serving the project's ASGI app on a random port.

    Returns ``(server_object, server_process, modified_settings)`` so the
    caller can stop the process and restore settings during teardown.
    """
    from functools import partial

    from channels.testing.live import make_application
    from daphne.testing import DaphneProcess
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
    from django.core.exceptions import ImproperlyConfigured
    from django.db import connections
    from django.test.utils import modify_settings

    host = "localhost"
    static_wrapper = ASGIStaticFilesHandler

    for connection in connections.all():
        if connection.vendor == "sqlite" and connection.is_in_memory_db():
            raise ImproperlyConfigured(
                "ChannelsLiveServer can not be used with in-memory databases"
            )

    modified_settings = modify_settings(ALLOWED_HOSTS={"append": host})
    modified_settings.enable()

    get_application = partial(make_application, static_wrapper=static_wrapper)
    server_process = DaphneProcess(
        host,
        get_application,
        setup=set_database_connection,
    )
    server_process.start()

    while True:
        if not server_process.ready.wait(timeout=1):
            if server_process.is_alive():
                continue
            raise RuntimeError("Server stopped") from None
        break

    port = server_process.port.value
    return _ChannelsLiveServer(host, port), server_process, modified_settings


@pytest.fixture(scope="session")
def channels_live_server(request):
    """Pytest fixture that provides a Channels live server for tests.

    Session-scoped: a single Daphne subprocess per pytest-xdist worker is
    started up-front and reused across all tests on that worker. Per-test
    DB isolation is provided by ``transactional_db`` on the consuming
    fixture (``admin_page`` / ``preauth_page`` / ``preauth_asgi_page``);
    the ASGI process talks to PostgreSQL via its own connection and
    always sees the post-TRUNCATE state between tests.

    Why session scope:
    - Function-scoped startup costs ~2 s per test for the Daphne fork +
      Django app load + ASGI routing + port allocation.
    - With ~74 Playwright tests using this fixture and ``-n auto`` running
      ~16 xdist workers, function scope causes resource pressure (16+
      simultaneous Daphne procs spawning + 16 chromium browsers + 16
      live_server procs) that triggers cascading ``Page.goto`` 30 s
      timeouts even on tests that have nothing to do with channels. In
      a measured run, function-scope dual-fixture: 90 fail / 4:59,
      session-scope single-fixture: 7 fail / 2:13.

    For the small minority of tests that genuinely need a fresh Daphne
    process per call (e.g. tests asserting on Daphne process startup
    output, or tests that close the WebSocket and need a clean channel
    layer), use ``channels_live_server_per_test``.
    """
    server, server_process, modified_settings = _spawn_daphne()
    try:
        yield server
    finally:
        server_process.terminate()
        server_process.join()
        modified_settings.disable()


@pytest.fixture
def channels_live_server_per_test(transactional_db):
    """Function-scoped variant: spawns a fresh Daphne subprocess per test.

    Use this only when a test specifically requires a brand-new ASGI
    process — typical reasons:
    - The test asserts on Daphne stdout/startup behaviour.
    - The test leaves WebSocket / channel-layer state that would confuse
      later tests sharing the same process.

    Default to ``channels_live_server`` (session-scoped) — it is ~2 s
    faster per test and significantly more stable under high-parallelism
    runs (no fork-storm pressure on the macOS / Linux scheduler).
    """
    server, server_process, modified_settings = _spawn_daphne()
    try:
        yield server
    finally:
        server_process.terminate()
        server_process.join()
        modified_settings.disable()
