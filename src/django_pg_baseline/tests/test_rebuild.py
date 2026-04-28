"""Unit tests for django_pg_baseline.rebuild."""

from __future__ import annotations

import sys

import pytest

from django_pg_baseline import rebuild as rebuild_module
from django_pg_baseline.conf import BaselineConfig
from django_pg_baseline.rebuild import (
    _freeze_timestamps,
    _run_pg_dump,
    _scrub_dump,
    rebuild_baseline,
)


@pytest.mark.parametrize(
    "input_text,expected",
    [
        (
            "\\restrict abc123\nCREATE TABLE foo;\n\\unrestrict abc123\n",
            "CREATE TABLE foo;\n",
        ),
        (
            "CREATE TABLE foo;\nINSERT INTO foo VALUES (1);\n",
            "CREATE TABLE foo;\nINSERT INTO foo VALUES (1);\n",
        ),
        (
            "\\restrict xyz\n",
            "",
        ),
        (
            "SET transaction_timeout = 0;\nCREATE TABLE foo;\n",
            "CREATE TABLE foo;\n",
        ),
    ],
)
def test_scrub_dump(tmp_path, input_text, expected):
    sql = tmp_path / "dump.sql"
    sql.write_text(input_text, encoding="utf-8")
    _scrub_dump(sql)
    assert sql.read_text(encoding="utf-8") == expected


def test_scrub_dump_preserves_non_restrict_backslash_lines(tmp_path):
    sql = tmp_path / "dump.sql"
    sql.write_text("\\connect bpp\nSELECT 1;\n", encoding="utf-8")
    _scrub_dump(sql)
    assert sql.read_text(encoding="utf-8") == "\\connect bpp\nSELECT 1;\n"


def test_run_pg_dump_invokes_docker_exec(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path / "out")
    db = {
        "USER": "bpp",
        "PASSWORD": "pw",
        "NAME": "bpp_baseline",
    }
    captured = {}

    def fake_run(cmd, check, stdout):
        captured["cmd"] = cmd
        captured["check"] = check
        stdout.write(b"-- dumped\n")

    monkeypatch.setattr(rebuild_module.subprocess, "run", fake_run)

    _run_pg_dump("container-abc123", db, cfg)

    assert captured["check"] is True
    assert captured["cmd"][0] == "docker"
    assert "container-abc123" in captured["cmd"]
    assert "pg_dump" in captured["cmd"]
    assert "bpp_baseline" in captured["cmd"]
    assert "--format=plain" in captured["cmd"]
    assert "PGPASSWORD=pw" in captured["cmd"]
    assert cfg.sql_path.exists()
    assert cfg.sql_path.read_bytes() == b"-- dumped\n"


class RecordingCursor:
    def __init__(self, regclass_map):
        self._map = regclass_map
        self.queries = []
        self._last_params = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.queries.append((sql, list(params) if params else []))
        if "to_regclass" in sql:
            table = params[0].replace("public.", "")
            self._last_result = (self._map.get(table),)
        else:
            self._last_result = None

    def fetchone(self):
        return self._last_result


class RecordingConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_freeze_timestamps_updates_existing_tables(monkeypatch, tmp_path):
    cfg = BaselineConfig(
        baseline_dir=tmp_path,
        freeze_timestamps=[
            ("django_migrations", ["applied"]),
            ("missing_table", ["ts"]),
        ],
        freeze_timestamp_value="2000-01-01 00:00:00+00",
    )

    cursor = RecordingCursor({"django_migrations": "django_migrations"})
    conn = RecordingConnection(cursor)

    import django.db as django_db

    monkeypatch.setattr(django_db, "connections", {"fake": conn})

    _freeze_timestamps("fake", cfg)

    update_queries = [q for q, _ in cursor.queries if q.startswith("UPDATE")]
    assert len(update_queries) == 1
    assert "django_migrations" in update_queries[0]
    assert "applied = %s::timestamptz" in update_queries[0]


def test_rebuild_baseline_missing_testcontainers(monkeypatch, tmp_path):
    cfg = BaselineConfig(baseline_dir=tmp_path)

    monkeypatch.setitem(sys.modules, "testcontainers", None)
    monkeypatch.setitem(sys.modules, "testcontainers.postgres", None)

    with pytest.raises(RuntimeError, match="testcontainers is required"):
        rebuild_baseline(cfg)
