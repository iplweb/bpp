import pytest
from django.db import DEFAULT_DB_ALIAS

# Fix for VCR.py compatibility with urllib3
# This resolves the AttributeError: 'VCRHTTPConnection' has no attribute 'debuglevel'


def set_database_connection():
    import os

    from django.conf import settings
    from django.db import connections

    test_db_name = "test_" + connections[DEFAULT_DB_ALIAS].settings_dict["NAME"]

    if os.environ.get("PYTEST_XDIST_WORKER", "master").startswith("gw"):
        test_db_name += "_" + os.environ.get("PYTEST_XDIST_WORKER")

    # with open("test.txt", "w") as f:
    #     f.write(test_db_name)
    settings.DATABASES["default"]["NAME"] = test_db_name


@pytest.fixture
def channels_live_server(transactional_db):
    """
    A pytest fixture that creates a channels live server for testing.

    This fixture properly initializes a Daphne server process with Django Channels
    support, handling all necessary setup and teardown operations.

    The fixture provides:
    - A running ASGI server accessible via HTTP and WebSocket protocols
    - Proper database configuration for the test environment
    - Automatic cleanup on test completion

    Returns:
        An object with the following attributes:
        - host: The server hostname (default: "localhost")
        - port: The dynamically assigned server port
        - url: The full HTTP URL (e.g., "http://localhost:8000")
        - live_server_url: Alias for url (for compatibility)
        - live_server_ws_url: The WebSocket URL (e.g., "ws://localhost:8000")
    """
    from functools import partial

    from channels.testing.live import make_application  # , set_database_connection
    from daphne.testing import DaphneProcess
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
    from django.core.exceptions import ImproperlyConfigured
    from django.db import connections
    from django.test.utils import modify_settings

    # Configuration
    host = "localhost"
    serve_static = True
    static_wrapper = ASGIStaticFilesHandler if serve_static else None

    # Check for in-memory databases (not supported with channels live server)
    for connection in connections.all():
        if connection.vendor == "sqlite" and connection.is_in_memory_db():
            raise ImproperlyConfigured(
                "ChannelsLiveServer can not be used with in-memory databases"
            )

    # Modify settings to allow the test host
    _live_server_modified_settings = modify_settings(ALLOWED_HOSTS={"append": host})
    _live_server_modified_settings.enable()

    # Create the application getter
    get_application = partial(
        make_application,
        static_wrapper=static_wrapper,
    )

    # Start the server process
    _server_process = DaphneProcess(
        host,
        get_application,
        setup=set_database_connection,
    )
    _server_process.start()

    # Wait for the server to be ready
    while True:
        if not _server_process.ready.wait(timeout=1):
            if _server_process.is_alive():
                continue
            raise RuntimeError("Server stopped") from None
        break

    # Get the dynamically assigned port
    port = _server_process.port.value

    # Create a server object with all necessary attributes
    class ChannelsLiveServer:
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

    server = ChannelsLiveServer(host, port)

    # Yield the server for test use
    yield server

    # Teardown: stop the server and restore settings
    _server_process.terminate()
    _server_process.join()
    _live_server_modified_settings.disable()
