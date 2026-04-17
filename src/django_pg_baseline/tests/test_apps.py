"""Unit tests for django_pg_baseline.apps."""

from __future__ import annotations

from pathlib import Path

from django_pg_baseline import conf as conf_module
from django_pg_baseline import patches as patches_module
from django_pg_baseline.apps import DjangoPgBaselineConfig
from django_pg_baseline.conf import BaselineConfig


def _make_app_config():
    return DjangoPgBaselineConfig.__new__(DjangoPgBaselineConfig)


def test_ready_exits_silently_on_missing_config(monkeypatch):
    def boom():
        raise RuntimeError("no PG_BASELINE")

    monkeypatch.setattr(conf_module, "get_config", boom)

    calls = []
    monkeypatch.setattr(
        patches_module, "install_test_db_patch", lambda cfg: calls.append(cfg)
    )

    app = _make_app_config()
    app.ready()
    assert calls == []


def test_ready_installs_patch_when_enabled_and_sql_exists(monkeypatch, tmp_path: Path):
    sql = tmp_path / "baseline.sql"
    sql.write_text("-- dump\n")
    cfg = BaselineConfig(baseline_dir=tmp_path, auto_load_on_test_db=True)

    monkeypatch.setattr(conf_module, "get_config", lambda: cfg)

    calls = []
    monkeypatch.setattr(
        patches_module, "install_test_db_patch", lambda c: calls.append(c)
    )

    _make_app_config().ready()
    assert calls == [cfg]


def test_ready_skips_when_auto_load_disabled(monkeypatch, tmp_path: Path):
    sql = tmp_path / "baseline.sql"
    sql.write_text("-- dump\n")
    cfg = BaselineConfig(baseline_dir=tmp_path, auto_load_on_test_db=False)

    monkeypatch.setattr(conf_module, "get_config", lambda: cfg)

    calls = []
    monkeypatch.setattr(
        patches_module, "install_test_db_patch", lambda c: calls.append(c)
    )

    _make_app_config().ready()
    assert calls == []


def test_ready_skips_when_sql_missing(monkeypatch, tmp_path: Path):
    cfg = BaselineConfig(baseline_dir=tmp_path, auto_load_on_test_db=True)
    monkeypatch.setattr(conf_module, "get_config", lambda: cfg)

    calls = []
    monkeypatch.setattr(
        patches_module, "install_test_db_patch", lambda c: calls.append(c)
    )

    _make_app_config().ready()
    assert calls == []
