"""Test fix dla session-scoped channels_live_server + pytest-django blocker.

Daphne fork-uje z parent pytest worker, dziedzicząc monkey-patch
``pytest_django._blocking_wrapper`` na ``BaseDatabaseWrapper.ensure_connection``.
Bez fix-a każde zapytanie do DB w subprocesie Daphne rzucało
``RuntimeError: Database access not allowed``.

Test weryfikuje że ``_restore_django_ensure_connection()`` cofnęło patch
na poziomie klasy. Symulujemy patch (jak pytest-django by go nałożył),
wołamy restore, sprawdzamy że ensure_connection już nie rzuca.
"""

import inspect

from django.db.backends.base.base import BaseDatabaseWrapper

from channels_live_server import _restore_django_ensure_connection


def test_restore_replaces_blocking_wrapper():
    original = BaseDatabaseWrapper.ensure_connection

    def fake_blocking_wrapper(*args, **kwargs):
        raise RuntimeError("Database access not allowed, use the django_db mark")

    BaseDatabaseWrapper.ensure_connection = fake_blocking_wrapper
    try:
        assert BaseDatabaseWrapper.ensure_connection is fake_blocking_wrapper

        _restore_django_ensure_connection()

        assert BaseDatabaseWrapper.ensure_connection is not fake_blocking_wrapper, (
            "Restore nie zadziałał — wciąż blocking wrapper"
        )
    finally:
        BaseDatabaseWrapper.ensure_connection = original


def test_restored_function_has_correct_signature():
    """Restored ensure_connection wymaga jednego argumentu (self)."""
    original = BaseDatabaseWrapper.ensure_connection
    try:
        _restore_django_ensure_connection()
        sig = inspect.signature(BaseDatabaseWrapper.ensure_connection)
        params = list(sig.parameters.keys())
        assert params == ["self"], f"Oczekiwano [self], dostałem {params}"
    finally:
        BaseDatabaseWrapper.ensure_connection = original
