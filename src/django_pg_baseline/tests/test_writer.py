"""Unit tests for django_pg_baseline.writer."""

from __future__ import annotations

import json
import subprocess

from django_pg_baseline import writer as writer_module
from django_pg_baseline.writer import (
    _git_sha,
    _postgres_version,
    collect_last_migrations,
    write_meta,
)


def test_git_sha_strips_output(monkeypatch):
    monkeypatch.setattr(
        writer_module.subprocess,
        "check_output",
        lambda *a, **kw: b"deadbeef\n",
    )
    assert _git_sha() == "deadbeef"


def test_git_sha_handles_called_process_error(monkeypatch):
    def boom(*a, **kw):
        raise subprocess.CalledProcessError(1, ["git"])

    monkeypatch.setattr(writer_module.subprocess, "check_output", boom)
    assert _git_sha() is None


def test_git_sha_handles_missing_git(monkeypatch):
    def boom(*a, **kw):
        raise FileNotFoundError

    monkeypatch.setattr(writer_module.subprocess, "check_output", boom)
    assert _git_sha() is None


class FakeCursor:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql):
        pass

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, row=("PostgreSQL 16.0",), raise_on_cursor=False):
        self._row = row
        self._raise = raise_on_cursor

    def cursor(self):
        if self._raise:
            raise RuntimeError("db down")
        return FakeCursor(self._row)


def test_postgres_version_returns_first_row(monkeypatch):
    from django.db import connection as django_connection

    monkeypatch.setattr(django_connection, "cursor", FakeConnection().cursor)
    assert _postgres_version() == "PostgreSQL 16.0"


def test_postgres_version_returns_none_on_exception(monkeypatch, capsys):
    from django.db import connection as django_connection

    broken = FakeConnection(raise_on_cursor=True)
    monkeypatch.setattr(django_connection, "cursor", broken.cursor)
    assert _postgres_version() is None
    out = capsys.readouterr().out
    assert "could not read postgres version" in out


def test_postgres_version_returns_none_when_no_row(monkeypatch):
    from django.db import connection as django_connection

    monkeypatch.setattr(django_connection, "cursor", FakeConnection(row=None).cursor)
    assert _postgres_version() is None


def test_collect_last_migrations_returns_max_per_app(monkeypatch):
    class FakeLoader:
        def __init__(self, connection=None, ignore_no_migrations=False):
            pass

        disk_migrations = [
            ("bpp", "0002_x"),
            ("bpp", "0003_y"),
            ("bpp", "0001_initial"),
            ("auth", "0001_initial"),
        ]

    import django.db.migrations.loader as loader_mod

    monkeypatch.setattr(loader_mod, "MigrationLoader", FakeLoader)

    assert collect_last_migrations() == {
        "auth": "0001_initial",
        "bpp": "0003_y",
    }


def test_write_meta_creates_json_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(writer_module, "_git_sha", lambda: "abc123")
    monkeypatch.setattr(writer_module, "_postgres_version", lambda: "PostgreSQL 16.0")
    monkeypatch.setattr(
        writer_module,
        "collect_last_migrations",
        lambda: {"bpp": "0001_initial"},
    )

    target = tmp_path / "nested" / "baseline.meta.json"
    write_meta(target)

    assert target.exists()
    text = target.read_text()
    assert text.endswith("\n")
    data = json.loads(text)
    assert data == {
        "git_sha": "abc123",
        "postgres_version": "PostgreSQL 16.0",
        "last_migration": {"bpp": "0001_initial"},
    }

    keys_in_order = list(data.keys())
    assert keys_in_order == sorted(keys_in_order)

    assert "wrote" in capsys.readouterr().out
