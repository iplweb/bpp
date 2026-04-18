"""Unit tests for django_pg_baseline.loader."""

from __future__ import annotations

import pytest

from django_pg_baseline import loader as loader_module
from django_pg_baseline.loader import baseline_needed, load_baseline


class FakeCursor:
    def __init__(self, fetch_result):
        self._fetch_result = fetch_result
        self.executed = []

    def execute(self, sql, *args, **kwargs):
        self.executed.append(sql)

    def fetchone(self):
        return self._fetch_result


def test_baseline_needed_when_table_missing():
    cur = FakeCursor((None,))
    assert baseline_needed(cur) is True
    assert "to_regclass" in cur.executed[0]


def test_baseline_needed_when_fetchone_none():
    cur = FakeCursor(None)
    assert baseline_needed(cur) is True


def test_baseline_needed_when_table_exists():
    cur = FakeCursor(("django_migrations",))
    assert baseline_needed(cur) is False


def test_load_baseline_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="Baseline dump not found"):
        load_baseline({"NAME": "db"}, tmp_path / "nope.sql")


class _FakeCompleted:
    returncode = 0


def test_load_baseline_invokes_psql(tmp_path, monkeypatch):
    dump = tmp_path / "baseline.sql"
    dump.write_text("-- dump\n")

    captured = {}

    def fake_run(cmd, env, check, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["check"] = check
        captured["kwargs"] = kwargs
        return _FakeCompleted()

    monkeypatch.setattr(loader_module.subprocess, "run", fake_run)

    dsn = {
        "HOST": "127.0.0.1",
        "PORT": 5433,
        "USER": "bpp",
        "PASSWORD": "secret",
        "NAME": "test_db",
    }
    load_baseline(dsn, dump)

    # load_baseline sets check=False and captures stdout so psql's "setval"
    # rows don't flood stderr; only the returncode is inspected, and on
    # nonzero it re-emits the captured stdout. The important contract is
    # that we pass the db name, single-transaction, ON_ERROR_STOP and the
    # dump file to psql through the right environment.
    assert captured["check"] is False
    assert captured["cmd"][0] == "psql"
    assert "-d" in captured["cmd"]
    assert "test_db" in captured["cmd"]
    assert "--single-transaction" in captured["cmd"]
    assert "ON_ERROR_STOP=1" in captured["cmd"]
    assert str(dump) in captured["cmd"]

    env = captured["env"]
    assert env["PGHOST"] == "127.0.0.1"
    assert env["PGPORT"] == "5433"
    assert env["PGUSER"] == "bpp"
    assert env["PGPASSWORD"] == "secret"


def test_load_baseline_defaults_for_missing_dsn_keys(tmp_path, monkeypatch):
    dump = tmp_path / "baseline.sql"
    dump.write_text("")

    captured = {}

    def fake_run(cmd, env, check, **kwargs):
        captured["env"] = env
        return _FakeCompleted()

    monkeypatch.setattr(loader_module.subprocess, "run", fake_run)

    load_baseline({"NAME": "db"}, dump)
    assert captured["env"]["PGHOST"] == "localhost"
    assert captured["env"]["PGPORT"] == "5432"
    assert captured["env"]["PGUSER"] == ""
    assert captured["env"]["PGPASSWORD"] == ""
