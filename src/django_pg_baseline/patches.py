"""Monkey-patch ``_create_test_db`` to preload a baseline pg_dump.

When pytest-django (or plain Django) creates a test database, we run
``psql -f baseline.sql`` against the freshly-empty DB so migrate only
applies the small delta of migrations added after the baseline was
dumped.
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
        test_database_name = original(self, verbosity, autoclobber, keepdb)

        import psycopg2

        dsn = self.connection.settings_dict
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
