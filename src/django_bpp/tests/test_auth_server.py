"""
Integration tests for the lightweight auth server.

Tests the is_superuser endpoint used by nginx auth_request
for protecting services like Grafana and Dozzle.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory


def test_auth_server_settings_import():
    """Verify auth_server settings module loads without errors."""
    from django_bpp.settings import auth_server

    assert auth_server.SECRET_KEY is not None
    assert auth_server.DATABASES is not None
    assert auth_server.AUTH_USER_MODEL == "bpp.BppUser"
    assert "bpp" in auth_server.INSTALLED_APPS


def test_is_superuser_unauthenticated_returns_unauthorized():
    """Unauthenticated requests should receive 401 Unauthorized."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = AnonymousUser()
    response = is_superuser(request)

    assert response.status_code == 401
    assert response.content == b"unauthorized"


@pytest.mark.django_db
def test_is_superuser_regular_user_gets_forbidden(test_user):
    """Non-superuser should receive 403 Forbidden."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = test_user
    response = is_superuser(request)

    assert response.status_code == 403
    assert response.content == b"forbidden"


@pytest.mark.django_db
def test_is_superuser_superuser_gets_ok_with_headers(superuser):
    """Superuser should receive 200 OK with user headers."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = superuser
    response = is_superuser(request)

    assert response.status_code == 200
    assert response.content == b"ok"
    assert response["X-WEBAUTH-USER"] == superuser.get_username()
    assert "X-WEBAUTH-EMAIL" in response
    assert "X-WEBAUTH-NAME" in response


@pytest.mark.django_db
def test_auth_server_health_endpoint_ok():
    """Healthy DB + Redis returns 200 with status ok."""
    import json

    from django_bpp.health import health_check

    rf = RequestFactory()
    request = rf.get("/health/")
    response = health_check(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


def test_health_check_returns_503_when_db_down(monkeypatch):
    """If DB ping fails, return 503 with the failing component."""
    import json

    from django_bpp import health

    # NIE patchujemy `health.connection.ensure_connection` — `connection` to
    # `ConnectionProxy` z `django.db`, którego `__setattr__` przekierowuje
    # zapis na realny `DatabaseWrapper` w `connections[default]`. Pytest
    # ``monkeypatch`` przy teardownie odtwarza „starą" wartość pobraną
    # przez ``getattr`` przez proxy — w teście bez ``@django_db`` to bound
    # ``pytest_django._blocking_wrapper``. ``setattr`` na proxy wstrzykuje
    # ten bound wrapper do ``connections[default].__dict__``, co nadpisuje
    # class-level patch i czyni ``django_db_blocker.unblock()``
    # nieskutecznym dla kolejnych testów na tym workerze (instance attr
    # ma priorytet) — pierwszy następny test używający DB pada na
    # ``RuntimeError: Database access not allowed`` w ``setup_databases``.
    # Patchujemy funkcję wyższego poziomu ``_check_db`` (symetrycznie do
    # ``test_health_check_returns_503_when_redis_down``).
    monkeypatch.setattr(health, "_check_db", lambda: "db: RuntimeError")
    monkeypatch.setattr(health, "_check_redis", lambda: None)

    rf = RequestFactory()
    response = health.health_check(rf.get("/health/"))

    assert response.status_code == 503
    body = json.loads(response.content)
    assert body["status"] == "error"
    assert any("db" in f for f in body["failures"])


def test_health_check_returns_503_when_redis_down(monkeypatch):
    """If Redis ping fails, return 503 with the failing component."""
    import json

    from django_bpp import health

    monkeypatch.setattr(health, "_check_db", lambda: None)
    monkeypatch.setattr(health, "_check_redis", lambda: "redis: ConnectionError")

    rf = RequestFactory()
    response = health.health_check(rf.get("/health/"))

    assert response.status_code == 503
    body = json.loads(response.content)
    assert body["status"] == "error"
    assert any("redis" in f for f in body["failures"])


def test_check_redis_skipped_without_broker_url():
    """Without CELERY_BROKER_URL (e.g. authserver settings), Redis check is
    skipped — returning None — instead of raising AttributeError.

    Regression test for: ``healthcheck: redis failed: AttributeError(
    "'Settings' object has no attribute 'CELERY_BROKER_URL'")``
    on the lightweight authserver.
    """
    from django.test.utils import override_settings

    from django_bpp import health

    # `override_settings(CELERY_BROKER_URL=None)` keeps the attribute defined
    # on the wrapper but maps it to None — exercises the falsy-value path.
    with override_settings(CELERY_BROKER_URL=None):
        assert health._check_redis() is None


def test_health_check_log_filter():
    """Test that UvicornHealthCheckFilter suppresses /health/ logs."""
    import logging

    from django_bpp.health import UvicornHealthCheckFilter

    f = UvicornHealthCheckFilter()

    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /health/ HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    assert f.filter(record) is False

    record_normal = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /api/v1/data HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    assert f.filter(record_normal) is True


def test_auth_server_has_rollbar_config():
    """
    Verify auth server settings include ROLLBAR configuration.

    The bpp app's ready() method calls configure_rollbar() which requires
    settings.ROLLBAR to exist. This test ensures the auth server settings
    include ROLLBAR to prevent AttributeError on startup.

    Regression test for: AttributeError: 'Settings' object has no attribute
    'ROLLBAR'
    """
    from django_bpp.settings import auth_server

    assert hasattr(auth_server, "ROLLBAR"), (
        "auth_server settings must include ROLLBAR configuration "
        "because bpp app is in INSTALLED_APPS and calls configure_rollbar()"
    )
    assert isinstance(auth_server.ROLLBAR, dict)
    assert "access_token" in auth_server.ROLLBAR
    assert "environment" in auth_server.ROLLBAR
