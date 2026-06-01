import pytest
from django.db import DEFAULT_DB_ALIAS

# Fix for VCR.py compatibility with urllib3
# This resolves the AttributeError: 'VCRHTTPConnection' has no attribute 'debuglevel'


def _restore_django_ensure_connection():
    """Cofnij monkey-patch ``pytest_django._blocking_wrapper`` w subprocesie.

    Daphne (``channels_live_server`` fixture, session-scoped od commit-a
    ``bafd8f209``) jest forkowany z pytest worker process-u. Dziedziczy
    monkey-patch na ``BaseDatabaseWrapper.ensure_connection``, który
    rzuca ``RuntimeError: Database access not allowed`` na każde
    zapytanie spoza testu z markerem ``django_db``.

    Konsekwencja: middleware używające DB w ``process_request``
    (``django_countdown``, ``first_run_wizard``, etc.) crashują na
    KAŻDYM żądaniu obsłużonym przez Daphne → 500 → puste strony →
    Playwright timeouts.

    Subprocess Daphne to dedykowany serwer testowy z własnym połączeniem
    do PG; nie odpalają się w nim żadne testy pytest, więc blocker nie
    chroni tu niczego — przeciwnie, sabotuje legitymalne żądania.
    Przywracamy oryginalną implementację ``ensure_connection`` z Django
    (bit-for-bit kopia z ``django.db.backends.base.base``).
    """
    from django.core.exceptions import ImproperlyConfigured  # noqa: F401
    from django.db.backends.base.base import BaseDatabaseWrapper

    def ensure_connection(self):
        """Guarantee that a connection to the database is established."""
        if self.connection is None:
            if self.in_atomic_block and self.closed_in_transaction:
                from django.db import ProgrammingError

                raise ProgrammingError(
                    "Cannot open a new connection in an atomic block."
                )
            with self.wrap_database_errors:
                self.connect()

    BaseDatabaseWrapper.ensure_connection = ensure_connection


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

    # Subprocess Daphne dziedziczy patch pytest-django blokujący DB.
    # Patrz docstring _restore_django_ensure_connection.
    _restore_django_ensure_connection()

    # Per-request invalidation cache'ów które session-scoped subprocess
    # trzyma w pamięci a które są wadliwe po `transactional_db` TRUNCATE
    # między testami. Bez tego: KeyError / ForeignKeyViolation gdy w
    # subprocesie zostaje stary mapping content_type_id → object,
    # a w bazie nowy test dostał inne id.
    _wire_per_request_cache_invalidation()


def _wire_per_request_cache_invalidation():
    """Wpina signal handler który czyści cache'y per request.

    ``ContentType.objects.clear_cache()`` jest najistotniejsze — Django
    cachuje mapowanie ``id``/``app_label``/``model`` → ``ContentType``
    instancja, a po ``transactional_db`` TRUNCATE w teście ID-y
    content_types w bazie się zmieniają. Stary cache w session-scoped
    Daphne process powoduje:

    - ``KeyError: '6'`` w ``ContentTypeManager.get_for_id`` (np.
      ``test_global_search_in_admin``).
    - ``ForeignKeyViolation`` przy zapisie do ``django_admin_log`` z
      ``content_type_id=70`` którego już nie ma w bazie (np.
      ``test_Wydawnictwo_Zwarte_Autor_Admin_forwarding_works``).

    Overhead clear_cache to single dict.clear() — pomijalny.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.core.signals import request_started

    def _clear_caches(sender, **kwargs):
        ContentType.objects.clear_cache()

    request_started.connect(_clear_caches, weak=False)


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
