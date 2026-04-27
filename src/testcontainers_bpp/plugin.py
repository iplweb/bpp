"""Pytest plugin that starts testcontainers for BPP tests.

**Enabled by default.** Disable with ``--no-testcontainers`` CLI flag or
``BPP_USE_TESTCONTAINERS=0`` environment variable.

**Ephemeral by default.** Containers are destroyed after pytest exits
(Ryuk sprząta nawet po Ctrl+C).  For faster re-runs, set
``BPP_TESTCONTAINERS_REUSE=1`` — containers persist between runs.

The plugin uses ``pytest_load_initial_conftests`` — the earliest pytest
hook — to start containers and inject their host:port into ``os.environ``
**before** ``--ds`` triggers ``django.setup()``.  This way
``django_bpp.settings.base`` reads the dynamic ports via its normal
``os.environ.get(...)`` calls and everything else (baseline loading,
xdist workers, denorm triggers) works unchanged.
"""

from __future__ import annotations

import atexit
import os

import pytest

_DISABLE_VALUES = {"0", "false", "no"}

# Module-level state so pytest_unconfigure can clean up.
_containers = None
_reuse = False


def _should_activate(args: list[str]) -> bool:
    """Active by default.  Disabled by env var or CLI flag."""
    if "--no-testcontainers" in args:
        return False
    env = os.environ.get("BPP_USE_TESTCONTAINERS", "").strip().lower()
    if env in _DISABLE_VALUES:
        return False
    return True


def pytest_addoption(parser):
    parser.addoption(
        "--no-testcontainers",
        action="store_true",
        default=False,
        help=(
            "Disable testcontainers — assume PostgreSQL, Redis, and "
            "RabbitMQ are already running (e.g. via docker-compose)."
        ),
    )


def _is_xdist_worker() -> bool:
    """Return True if running inside a pytest-xdist worker process.

    Workers inherit the env vars set by the controller, so they already
    have the correct host:port — no need to start new containers.
    """
    return "PYTEST_XDIST_WORKER" in os.environ


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):  # noqa: ARG001
    """Uruchom testcontainery i wstrzyknij ich porty do os.environ.

    UWAGA: dekorator ``@pytest.hookimpl(tryfirst=True)`` jest niezbędny.

    Pytest-django ma własny hook ``pytest_load_initial_conftests``, w
    którym wymusza załadowanie ustawień Django (``dj_settings.DATABASES``,
    pytest_django/plugin.py:357).  To powoduje import modułu
    ``django_bpp.settings.base``, który czyta parametry połączenia z
    ``os.environ`` w momencie importu — np. ``env("DJANGO_BPP_DB_PORT")``
    w linii 679.

    Deweloper zazwyczaj ma w shellu (przez direnv / ``.env``)
    ``DJANGO_BPP_DB_PORT=5432`` — domyślny port docker-compose.  Jeżeli
    Django załaduje ustawienia ZANIM ta funkcja ustawi porty z
    testcontainerów, to Django połączy się z portem 5432 (albo dostanie
    „Connection refused" gdy docker-compose nie działa).  Dynamiczny port
    z testcontainerów (np. 63403) nigdy nie dotrze do Django.

    Dzięki ``tryfirst=True`` gwarantujemy, że ta funkcja wykona się
    PRZED hookiem pytest-django:
    1. Startujemy testcontainery → dostajemy losowe porty (np. pg=63403)
    2. Nadpisujemy os.environ["DJANGO_BPP_DB_PORT"] = "63403"
    3. Ustawiamy os.environ["DJANGO_BPP_SKIP_DOTENV"] = "1", żeby
       ``environ.Env.read_env(.env, overwrite=True)`` w base.py nie
       nadpisał naszych wartości z powrotem na 5432
    4. DOPIERO POTEM odpala się hook pytest-django, importuje ustawienia
       Django i Django czyta prawidłowe porty testcontainerów z os.environ
    """
    if not _should_activate(args):
        return

    # Workery xdist dziedziczą zmienne środowiskowe od kontrolera —
    # pomijamy tworzenie kontenerów, ale DJANGO_BPP_SKIP_DOTENV
    # musi być ustawione.
    if _is_xdist_worker():
        os.environ["DJANGO_BPP_SKIP_DOTENV"] = "1"
        return

    global _containers, _reuse  # noqa: PLW0603

    try:
        from .containers import DockerNotRunningError, start_containers
    except ImportError as exc:
        raise RuntimeError(
            "testcontainers is required (enabled by default). "
            "Install with: uv sync --extra dev\n"
            "Or disable with: --no-testcontainers"
        ) from exc

    _reuse = os.environ.get("BPP_TESTCONTAINERS_REUSE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    try:
        _containers = start_containers(reuse=_reuse)
    except DockerNotRunningError as exc:
        raise pytest.UsageError(
            "[testcontainers-bpp] Docker daemon is not reachable. "
            "Is Docker Desktop running?\n"
            "  - Start Docker Desktop and re-run pytest, OR\n"
            "  - Disable testcontainers: set BPP_USE_TESTCONTAINERS=0 "
            "or pass --no-testcontainers (requires docker-compose "
            "services running locally).\n"
            f"Underlying error: {exc}"
        ) from None

    # Safety net: pytest_unconfigure nie odpala się przy abrupt-exit
    # (sys.exit z fixture, nieprzechwycony wyjątek, OOM killer na pytest).
    # Ryuk bywa niezawodny tylko dopóki sam żyje — przy restarcie Docker
    # Desktop również ginie. atexit łapie większość cichych padów, gdzie
    # sam proces pytest kończy się normalnie. Nie chroni przed SIGKILL.
    atexit.register(_atexit_stop)

    # Wstrzykujemy dane połączeniowe do os.environ ZANIM django.setup()
    # załaduje ustawienia.
    os.environ["DJANGO_BPP_DB_HOST"] = _containers.pg_host
    os.environ["DJANGO_BPP_DB_PORT"] = str(_containers.pg_port)
    os.environ["DJANGO_BPP_DB_USER"] = "bpp"
    os.environ["DJANGO_BPP_DB_PASSWORD"] = "password"
    os.environ["DJANGO_BPP_DB_NAME"] = "bpp"

    # Baseline jest ładowane do bazy `bpp` wewnątrz kontenera przez
    # /docker-entrypoint-initdb.d/. Mówimy Django, żeby tworzył
    # `test_bpp` jako klon `bpp` przez CREATE DATABASE ... WITH TEMPLATE
    # bpp — to natywna operacja Postgresa, instant, bez psql.
    os.environ["DJANGO_BPP_TEST_TEMPLATE"] = "bpp"

    os.environ["DJANGO_BPP_REDIS_HOST"] = _containers.redis_host
    os.environ["DJANGO_BPP_REDIS_PORT"] = str(_containers.redis_port)

    os.environ["DJANGO_BPP_RABBITMQ_HOST"] = _containers.rabbitmq_host
    os.environ["DJANGO_BPP_RABBITMQ_PORT"] = str(_containers.rabbitmq_port)
    os.environ["DJANGO_BPP_RABBITMQ_USER"] = "bpp"
    os.environ["DJANGO_BPP_RABBITMQ_PASS"] = "bpp"

    # Pomijamy ładowanie pliku .env — sami dostarczamy wszystkie dane.
    os.environ["DJANGO_BPP_SKIP_DOTENV"] = "1"


def _atexit_stop() -> None:
    """Backup cleanup triggered when pytest process exits without pytest_unconfigure."""
    global _containers  # noqa: PLW0603

    if _containers is None or _reuse:
        return

    try:
        from .containers import stop_containers

        stop_containers(_containers)
    except Exception:
        import traceback

        traceback.print_exc()
    finally:
        _containers = None


def pytest_unconfigure(config):  # noqa: ARG001
    global _containers  # noqa: PLW0603

    if _containers is None:
        return

    if _reuse:
        # In reuse mode, containers survive for the next run.
        return

    from .containers import stop_containers

    stop_containers(_containers)
    _containers = None
