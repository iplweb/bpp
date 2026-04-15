"""Unit tests for django_pg_baseline.pytest_plugin."""

from __future__ import annotations

from pathlib import Path

from django_pg_baseline import pytest_plugin as plugin_module
from django_pg_baseline.conf import BaselineConfig


def _run_configure(monkeypatch, cfg):
    setup_calls = []
    install_calls = []

    import django

    monkeypatch.setattr(django, "setup", lambda: setup_calls.append(True))

    from django_pg_baseline import conf as conf_module
    from django_pg_baseline import patches as patches_module

    monkeypatch.setattr(conf_module, "get_config", lambda: cfg)
    monkeypatch.setattr(
        patches_module,
        "install_test_db_patch",
        lambda c: install_calls.append(c),
    )

    plugin_module.pytest_configure(config=None)
    return setup_calls, install_calls


def test_pytest_configure_installs_patch(monkeypatch, tmp_path: Path):
    sql = tmp_path / "baseline.sql"
    sql.write_text("-- dump\n")
    cfg = BaselineConfig(baseline_dir=tmp_path, auto_load_on_test_db=True)

    setup_calls, install_calls = _run_configure(monkeypatch, cfg)
    assert setup_calls == [True]
    assert install_calls == [cfg]


def test_pytest_configure_skips_when_auto_load_disabled(monkeypatch, tmp_path: Path):
    sql = tmp_path / "baseline.sql"
    sql.write_text("-- dump\n")
    cfg = BaselineConfig(baseline_dir=tmp_path, auto_load_on_test_db=False)

    setup_calls, install_calls = _run_configure(monkeypatch, cfg)
    assert setup_calls == [True]
    assert install_calls == []


def test_pytest_configure_skips_when_sql_missing(monkeypatch, tmp_path: Path):
    cfg = BaselineConfig(baseline_dir=tmp_path, auto_load_on_test_db=True)
    setup_calls, install_calls = _run_configure(monkeypatch, cfg)
    assert setup_calls == [True]
    assert install_calls == []
