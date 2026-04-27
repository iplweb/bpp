"""Unit tests for django_pg_baseline.patches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from django_pg_baseline import patches as patches_module
from django_pg_baseline.conf import BaselineConfig
from django_pg_baseline.patches import install_test_db_patch


@pytest.fixture(autouse=True)
def reset_patch_state(monkeypatch):
    from django.db.backends.base import creation as _creation

    monkeypatch.setattr(patches_module, "_already_patched", False)
    original = _creation.BaseDatabaseCreation._create_test_db
    yield
    _creation.BaseDatabaseCreation._create_test_db = original
    monkeypatch.setattr(patches_module, "_already_patched", False)


@pytest.fixture
def config_with_sql(tmp_path: Path) -> BaselineConfig:
    sql = tmp_path / "baseline.sql"
    sql.write_text("-- dump\n")
    return BaselineConfig(baseline_dir=tmp_path)


class FakePsycopg2Module:
    class OperationalError(Exception):
        pass

    def __init__(self, fetch_result=("django_migrations",), raise_on_connect=False):
        self._fetch = fetch_result
        self._raise = raise_on_connect
        self.connect_calls = []

    def connect(self, **kwargs):
        self.connect_calls.append(kwargs)
        if self._raise:
            raise self.OperationalError("cannot connect")
        fetch = self._fetch

        class FakeCursor:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def execute(self_inner, sql):
                pass

            def fetchone(self_inner):
                return fetch

        class FakeConn:
            def cursor(self_inner):
                return FakeCursor()

            def close(self_inner):
                pass

        return FakeConn()


class FakeCreation:
    def __init__(self, dsn=None):
        self.connection = SimpleNamespace(
            settings_dict=dsn
            or {
                "HOST": "localhost",
                "PORT": 5432,
                "USER": "bpp",
                "PASSWORD": "p",
                "NAME": "main",
            }
        )


def _call_patched(verbosity=1, autoclobber=False, keepdb=False):
    from django.db.backends.base import creation as _creation

    return _creation.BaseDatabaseCreation._create_test_db(
        FakeCreation(), verbosity, autoclobber, keepdb
    )


def test_install_noop_when_sql_missing(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)

    from django.db.backends.base import creation as _creation

    original = _creation.BaseDatabaseCreation._create_test_db
    install_test_db_patch(cfg)
    assert _creation.BaseDatabaseCreation._create_test_db is original
    assert patches_module._already_patched is False


def test_install_is_idempotent(config_with_sql, monkeypatch):
    from django.db.backends.base import creation as _creation

    monkeypatch.setattr(
        _creation.BaseDatabaseCreation,
        "_create_test_db",
        lambda self, verbosity, autoclobber, keepdb=False: "marker_db",
    )

    install_test_db_patch(config_with_sql)
    first = _creation.BaseDatabaseCreation._create_test_db
    install_test_db_patch(config_with_sql)
    second = _creation.BaseDatabaseCreation._create_test_db
    assert first is second
    assert patches_module._already_patched is True


def test_patch_loads_baseline_when_db_is_empty(config_with_sql, monkeypatch):
    from django.db.backends.base import creation as _creation

    monkeypatch.setattr(
        _creation.BaseDatabaseCreation,
        "_create_test_db",
        lambda self, verbosity, autoclobber, keepdb=False: "test_main",
    )

    fake_psy = FakePsycopg2Module(fetch_result=(None,))
    monkeypatch.setitem(__import__("sys").modules, "psycopg2", fake_psy)

    load_calls = []
    monkeypatch.setattr(
        patches_module,
        "load_baseline",
        lambda dsn, path: load_calls.append((dict(dsn), path)),
    )

    install_test_db_patch(config_with_sql)
    result = _call_patched()

    assert result == "test_main"
    assert len(load_calls) == 1
    dsn_passed, path_passed = load_calls[0]
    assert dsn_passed["NAME"] == "test_main"
    assert path_passed == config_with_sql.sql_path


def test_patch_skips_load_when_db_already_populated(config_with_sql, monkeypatch):
    from django.db.backends.base import creation as _creation

    monkeypatch.setattr(
        _creation.BaseDatabaseCreation,
        "_create_test_db",
        lambda self, verbosity, autoclobber, keepdb=False: "test_main",
    )

    fake_psy = FakePsycopg2Module(fetch_result=("django_migrations",))
    monkeypatch.setitem(__import__("sys").modules, "psycopg2", fake_psy)

    load_calls = []
    monkeypatch.setattr(
        patches_module,
        "load_baseline",
        lambda dsn, path: load_calls.append((dsn, path)),
    )

    install_test_db_patch(config_with_sql)
    result = _call_patched()

    assert result == "test_main"
    assert load_calls == []


class FakeNodbCursor:
    def __init__(self, log: list[tuple[str, list]]):
        self._log = log

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self._log.append((sql, list(params) if params else []))


class FakeCreationWithTemplate:
    """FakeCreation analogue exercising the WITH TEMPLATE code path."""

    def __init__(self, executed_sql: list[tuple[str, list]]):
        self.executed = executed_sql
        self.connection = SimpleNamespace(
            settings_dict={
                "HOST": "localhost",
                "PORT": 5432,
                "USER": "bpp",
                "PASSWORD": "p",
                "NAME": "main",
                "TEST": {"TEMPLATE": "main"},
            },
            close=lambda: executed_sql.append(("close", [])),
            close_pool=lambda: executed_sql.append(("close_pool", [])),
        )

    def _nodb_cursor(self):
        return FakeNodbCursor(self.executed)


def test_patch_terminates_template_connections_when_using_template(
    config_with_sql, monkeypatch
):
    from django.db.backends.base import creation as _creation

    create_calls = []

    def fake_original(self, verbosity, autoclobber, keepdb=False):
        create_calls.append("create")
        return "test_main"

    monkeypatch.setattr(
        _creation.BaseDatabaseCreation, "_create_test_db", fake_original
    )

    fake_psy = FakePsycopg2Module(fetch_result=("django_migrations",))
    monkeypatch.setitem(__import__("sys").modules, "psycopg2", fake_psy)

    load_calls = []
    monkeypatch.setattr(
        patches_module,
        "load_baseline",
        lambda dsn, path: load_calls.append((dsn, path)),
    )

    install_test_db_patch(config_with_sql)

    executed: list[tuple[str, list]] = []
    fake = FakeCreationWithTemplate(executed)
    result = _creation.BaseDatabaseCreation._create_test_db(fake, 1, False, False)

    assert result == "test_main"
    # Connection was closed before CREATE DATABASE WITH TEMPLATE.
    assert ("close", []) in executed
    assert ("close_pool", []) in executed
    # pg_terminate_backend was issued against the template DB.
    sql_strings = [item[0] for item in executed if isinstance(item[0], str)]
    assert any("pg_terminate_backend" in s for s in sql_strings)
    # …with the template name as the parameter, not the test DB.
    terminate_call = next(
        item for item in executed if "pg_terminate_backend" in item[0]
    )
    assert terminate_call[1] == ["main"]
    # The CREATE DATABASE itself happened (delegated to original).
    assert create_calls == ["create"]
    # Template path → DB already populated (from clone) → no psql reload.
    assert load_calls == []


def test_patch_handles_operational_error(config_with_sql, monkeypatch):
    from django.db.backends.base import creation as _creation

    monkeypatch.setattr(
        _creation.BaseDatabaseCreation,
        "_create_test_db",
        lambda self, verbosity, autoclobber, keepdb=False: "test_main",
    )

    fake_psy = FakePsycopg2Module(raise_on_connect=True)
    monkeypatch.setitem(__import__("sys").modules, "psycopg2", fake_psy)

    load_calls = []
    monkeypatch.setattr(
        patches_module,
        "load_baseline",
        lambda dsn, path: load_calls.append((dsn, path)),
    )

    install_test_db_patch(config_with_sql)
    result = _call_patched()

    assert result == "test_main"
    assert load_calls == []
