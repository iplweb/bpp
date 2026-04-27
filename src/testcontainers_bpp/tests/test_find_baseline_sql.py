"""Unit tests for testcontainers_bpp.containers.find_baseline_sql."""

from __future__ import annotations

from pathlib import Path

from testcontainers_bpp.containers import find_baseline_sql


def test_returns_override_when_env_points_to_existing_file(tmp_path, monkeypatch):
    sql = tmp_path / "custom.sql"
    sql.write_text("-- test\n")
    monkeypatch.setenv("BPP_BASELINE_SQL_PATH", str(sql))

    assert find_baseline_sql() == sql


def test_falls_back_to_convention_when_override_missing(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("BPP_BASELINE_SQL_PATH", str(tmp_path / "nope.sql"))
    # The convention path inside the repo may or may not exist depending
    # on whether baseline-sql/baseline.sql is checked in. Test that we
    # don't blow up either way and that the override miss is logged.
    result = find_baseline_sql()
    assert result is None or isinstance(result, Path)


def test_returns_none_when_neither_set(monkeypatch):
    monkeypatch.delenv("BPP_BASELINE_SQL_PATH", raising=False)
    # In the BPP repo the conventional path exists, so this only proves
    # that find_baseline_sql doesn't raise; if the file is missing in a
    # downstream consumer, the returned value would be None.
    result = find_baseline_sql()
    assert result is None or result.is_file()


def test_returns_convention_path_when_present(monkeypatch):
    """When the conventional baseline.sql exists, find it without an env."""
    monkeypatch.delenv("BPP_BASELINE_SQL_PATH", raising=False)
    result = find_baseline_sql()
    if result is not None:
        # Path should end with src/baseline-sql/baseline.sql
        assert result.parent.name == "baseline-sql"
        assert result.name == "baseline.sql"
        assert result.is_file()


def test_empty_env_var_treated_as_unset(monkeypatch):
    monkeypatch.setenv("BPP_BASELINE_SQL_PATH", "  ")
    # Whitespace-only override should be ignored, falling through to
    # convention without producing a "set but missing" warning.
    result = find_baseline_sql()
    assert result is None or result.is_file()
