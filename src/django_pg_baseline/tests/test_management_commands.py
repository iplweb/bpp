"""Tests for django_pg_baseline management commands."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command

from django_pg_baseline.conf import BaselineConfig
from django_pg_baseline.freshness import FreshnessReport
from django_pg_baseline.management.commands import baseline_check as cmd_check
from django_pg_baseline.management.commands import baseline_info as cmd_info
from django_pg_baseline.management.commands import baseline_load as cmd_load
from django_pg_baseline.management.commands import baseline_rebuild as cmd_rebuild


def _patch_config(monkeypatch, cfg):
    monkeypatch.setattr(cmd_check, "get_config", lambda: cfg)
    monkeypatch.setattr(cmd_info, "get_config", lambda: cfg)
    monkeypatch.setattr(cmd_load, "get_config", lambda: cfg)
    monkeypatch.setattr(cmd_rebuild, "get_config", lambda: cfg)


def _ok_report():
    return FreshnessReport(
        ok=True,
        max_delta=50,
        deltas={"bpp": 3},
        over={},
        git_sha="abc",
        worst_app="bpp",
        worst_delta=3,
        meta={"git_sha": "abc"},
    )


def _stale_report():
    return FreshnessReport(
        ok=False,
        max_delta=5,
        deltas={"bpp": 100, "auth": 2},
        over={"bpp": 100},
        git_sha="abc",
        worst_app="bpp",
        worst_delta=100,
        meta={"git_sha": "abc"},
    )


def test_baseline_check_missing_meta_exits_with_1(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)

    with pytest.raises(SystemExit) as exc:
        call_command("baseline_check")
    assert exc.value.code == 1


def test_baseline_check_ok(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)
    monkeypatch.setattr(cmd_check, "check_freshness", lambda *a, **kw: _ok_report())

    out = StringIO()
    call_command("baseline_check", stdout=out)
    text = out.getvalue()
    assert "OK" in text
    assert "bpp" in text


def test_baseline_check_stale_exits_with_1(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)
    monkeypatch.setattr(cmd_check, "check_freshness", lambda *a, **kw: _stale_report())

    out = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("baseline_check", stdout=out)
    assert exc.value.code == 1
    assert "STALE" in out.getvalue()
    assert "bpp" in out.getvalue()


def test_baseline_check_max_delta_override(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path, freshness_max_delta=50)
    _patch_config(monkeypatch, cfg)

    captured = {}

    def fake_check(threshold, path):
        captured["threshold"] = threshold
        return _ok_report()

    monkeypatch.setattr(cmd_check, "check_freshness", fake_check)

    call_command("baseline_check", "--max-delta", "999", stdout=StringIO())
    assert captured["threshold"] == 999


def test_baseline_info_missing_meta(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)
    err = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("baseline_info", stderr=err)
    assert exc.value.code == 1
    assert "not found" in err.getvalue()


def test_baseline_info_happy_path(tmp_path, monkeypatch, fake_meta_dict):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    cfg.meta_path.write_text(json.dumps(fake_meta_dict))
    _patch_config(monkeypatch, cfg)
    monkeypatch.setattr(cmd_info, "check_freshness", lambda *a, **kw: _ok_report())

    out = StringIO()
    call_command("baseline_info", stdout=out)
    text = out.getvalue()
    assert "deadbeef" in text
    assert "PostgreSQL 16.0" in text
    assert "Worst delta" in text
    assert "bpp" in text


class FakeCursor:
    def __init__(self, fetch_result):
        self._fetch_result = fetch_result

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql):
        pass

    def fetchone(self):
        return self._fetch_result


class FakeConnection:
    def __init__(self, fetch_result):
        self._fetch_result = fetch_result
        self.settings_dict = {
            "HOST": "localhost",
            "PORT": 5432,
            "USER": "bpp",
            "PASSWORD": "",
            "NAME": "bpp_test",
        }

    def cursor(self):
        return FakeCursor(self._fetch_result)


def _patch_connections(monkeypatch, module, fake):
    class FakeConnections:
        def __getitem__(self, alias):
            return fake

    monkeypatch.setattr(module, "connections", FakeConnections())


def test_baseline_load_skips_when_populated(tmp_path, monkeypatch, fake_sql_file):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)
    _patch_connections(monkeypatch, cmd_load, FakeConnection(("django_migrations",)))

    load_calls = []
    monkeypatch.setattr(
        cmd_load, "load_baseline", lambda *a, **kw: load_calls.append(a)
    )

    out = StringIO()
    call_command("baseline_load", stdout=out)
    assert load_calls == []
    assert "skipping" in out.getvalue()


def test_baseline_load_invokes_loader_when_empty(tmp_path, monkeypatch, fake_sql_file):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)
    _patch_connections(monkeypatch, cmd_load, FakeConnection((None,)))

    load_calls = []
    monkeypatch.setattr(
        cmd_load, "load_baseline", lambda dsn, path: load_calls.append((dsn, path))
    )

    call_command("baseline_load", stdout=StringIO())
    assert len(load_calls) == 1
    assert load_calls[0][1] == cfg.sql_path


def test_baseline_load_force_skips_probe(tmp_path, monkeypatch, fake_sql_file):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)
    _patch_connections(monkeypatch, cmd_load, FakeConnection(("django_migrations",)))

    load_calls = []
    monkeypatch.setattr(
        cmd_load, "load_baseline", lambda dsn, path: load_calls.append((dsn, path))
    )

    call_command("baseline_load", "--force", stdout=StringIO())
    assert len(load_calls) == 1


def test_baseline_load_exits_when_sql_missing(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)
    _patch_connections(monkeypatch, cmd_load, FakeConnection((None,)))

    def boom(dsn, path):
        raise FileNotFoundError("no dump")

    monkeypatch.setattr(cmd_load, "load_baseline", boom)

    err = StringIO()
    with pytest.raises(SystemExit) as exc:
        call_command("baseline_load", stderr=err)
    assert exc.value.code == 1
    assert "no dump" in err.getvalue()


def test_baseline_rebuild_invokes_rebuild(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)

    calls = []
    monkeypatch.setattr(cmd_rebuild, "rebuild_baseline", lambda c: calls.append(c))

    call_command("baseline_rebuild", stdout=StringIO())
    assert calls == [cfg]
    assert calls[0].rebuild_image == cfg.rebuild_image


def test_baseline_rebuild_image_override(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)

    calls = []
    monkeypatch.setattr(cmd_rebuild, "rebuild_baseline", lambda c: calls.append(c))

    call_command("baseline_rebuild", "--image", "postgres:15", stdout=StringIO())
    assert calls[0].rebuild_image == "postgres:15"


def test_baseline_rebuild_baseline_dir_override(tmp_path, monkeypatch):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    _patch_config(monkeypatch, cfg)

    calls = []
    monkeypatch.setattr(cmd_rebuild, "rebuild_baseline", lambda c: calls.append(c))

    other = tmp_path / "other"
    call_command("baseline_rebuild", "--baseline-dir", str(other), stdout=StringIO())
    assert calls[0].baseline_dir == other
