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
