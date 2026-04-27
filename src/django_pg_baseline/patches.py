"""Monkey-patch ``_create_test_db`` to preload a baseline pg_dump.

When pytest-django (or plain Django) creates a test database, we run
``psql -f baseline.sql`` against the freshly-empty DB so migrate only
applies the small delta of migrations added after the baseline was
dumped.

When ``DATABASES['default']['TEST']['TEMPLATE']`` is set (e.g. by
``testcontainers_bpp`` after mounting baseline.sql into the PG init
scripts), Django runs ``CREATE DATABASE … WITH TEMPLATE`` instead.
The patch then sees a populated ``test_*`` database and skips the
``psql`` reload — but it first kicks any other sessions off the
template database so Postgres allows the WITH TEMPLATE clone.
"""

from __future__ import annotations

from .conf import BaselineConfig
from .loader import load_baseline

_already_patched = False


def install_test_db_patch(config: BaselineConfig) -> None:
    """Install (idempotently) the ``_create_test_db`` monkey patch."""
    global _already_patched
    if _already_patched:
        return
    if not config.sql_path.exists():
        return

    from django.db.backends.base import creation as _creation

    original = _creation.BaseDatabaseCreation._create_test_db

    def _create_test_db_with_baseline(self, verbosity, autoclobber, keepdb=False):
        # If the test database is to be cloned via ``CREATE DATABASE …
        # WITH TEMPLATE bpp`` (typical when ``testcontainers_bpp`` mounts
        # baseline.sql into the PG init scripts), Postgres requires no
        # other sessions on the source database. Boot the default
        # Django connection off bpp and kick any leftover backends
        # (e.g. autovacuum, lingering wait-strategy connection) before
        # delegating to Django's CREATE DATABASE.
        dsn = self.connection.settings_dict
        template = (dsn.get("TEST") or {}).get("TEMPLATE")
        if template:
            self.connection.close()
            close_pool = getattr(self.connection, "close_pool", None)
            if callable(close_pool):
                close_pool()
            with self._nodb_cursor() as cursor:
                cursor.execute(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    [template],
                )

        test_database_name = original(self, verbosity, autoclobber, keepdb)

        import psycopg2

        try:
            inspect = psycopg2.connect(
                host=dsn.get("HOST") or "localhost",
                port=dsn.get("PORT") or 5432,
                user=dsn.get("USER"),
                password=dsn.get("PASSWORD") or "",
                dbname=test_database_name,
            )
        except psycopg2.OperationalError:
            # Test DB isn't reachable via direct psycopg2 — let Django's
            # normal migrate-from-scratch path take over.
            return test_database_name

        try:
            with inspect.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.django_migrations')")
                row = cursor.fetchone()
            empty = row is None or row[0] is None
        finally:
            inspect.close()

        if empty:
            load_baseline(
                {**dsn, "NAME": test_database_name},
                config.sql_path,
            )

        return test_database_name

    _creation.BaseDatabaseCreation._create_test_db = _create_test_db_with_baseline
    _already_patched = True
