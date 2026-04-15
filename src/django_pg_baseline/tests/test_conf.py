"""Unit tests for django_pg_baseline.conf."""

from __future__ import annotations

from pathlib import Path

import pytest

from django_pg_baseline import conf as conf_module
from django_pg_baseline.conf import (
    DEFAULT_DATABASE_ALIAS,
    DEFAULT_FRESHNESS_MAX_DELTA,
    DEFAULT_META_FILENAME,
    DEFAULT_PG_DUMP_EXTRA_ARGS,
    DEFAULT_REBUILD_IMAGE,
    DEFAULT_SQL_FILENAME,
    BaselineConfig,
    get_config,
)


def test_get_config_requires_baseline_dir(settings):
    settings.PG_BASELINE = {}
    with pytest.raises(RuntimeError, match="BASELINE_DIR"):
        get_config()


def test_get_config_missing_setting(settings):
    if hasattr(settings, "PG_BASELINE"):
        del settings.PG_BASELINE
    with pytest.raises(RuntimeError, match="BASELINE_DIR"):
        get_config()


def test_get_config_defaults(settings, tmp_path):
    settings.PG_BASELINE = {"BASELINE_DIR": str(tmp_path)}
    cfg = get_config()

    assert isinstance(cfg, BaselineConfig)
    assert cfg.baseline_dir == Path(tmp_path)
    assert cfg.sql_filename == DEFAULT_SQL_FILENAME
    assert cfg.meta_filename == DEFAULT_META_FILENAME
    assert cfg.database_alias == DEFAULT_DATABASE_ALIAS
    assert cfg.auto_load_on_test_db is True
    assert cfg.freshness_max_delta == DEFAULT_FRESHNESS_MAX_DELTA
    assert cfg.rebuild_image == DEFAULT_REBUILD_IMAGE
    assert cfg.pg_dump_extra_args == DEFAULT_PG_DUMP_EXTRA_ARGS
    assert cfg.freeze_timestamps == [("django_migrations", ["applied"])]
    assert cfg.freeze_timestamp_value == "2000-01-01 00:00:00+00"


def test_get_config_overrides(settings, tmp_path):
    settings.PG_BASELINE = {
        "BASELINE_DIR": str(tmp_path),
        "SQL_FILENAME": "snap.sql",
        "META_FILENAME": "snap.json",
        "DATABASE_ALIAS": "other",
        "AUTO_LOAD_ON_TEST_DB": False,
        "FRESHNESS_MAX_DELTA": "10",
        "REBUILD_IMAGE": "postgres:15",
        "FREEZE_TIMESTAMP_VALUE": "1999-01-01 00:00:00+00",
    }
    cfg = get_config()
    assert cfg.sql_filename == "snap.sql"
    assert cfg.meta_filename == "snap.json"
    assert cfg.database_alias == "other"
    assert cfg.auto_load_on_test_db is False
    assert cfg.freshness_max_delta == 10
    assert cfg.rebuild_image == "postgres:15"
    assert cfg.freeze_timestamp_value == "1999-01-01 00:00:00+00"


def test_pg_dump_extra_exclude_table_data_stacks(settings, tmp_path):
    settings.PG_BASELINE = {
        "BASELINE_DIR": str(tmp_path),
        "PG_DUMP_EXTRA_EXCLUDE_TABLE_DATA": ["foo_*", "bar"],
    }
    cfg = get_config()
    assert cfg.pg_dump_extra_args[: len(DEFAULT_PG_DUMP_EXTRA_ARGS)] == (
        DEFAULT_PG_DUMP_EXTRA_ARGS
    )
    assert "--exclude-table-data=foo_*" in cfg.pg_dump_extra_args
    assert "--exclude-table-data=bar" in cfg.pg_dump_extra_args


def test_pg_dump_extra_args_replaces_defaults(settings, tmp_path):
    settings.PG_BASELINE = {
        "BASELINE_DIR": str(tmp_path),
        "PG_DUMP_EXTRA_ARGS": ["--custom"],
    }
    cfg = get_config()
    assert cfg.pg_dump_extra_args == ["--custom"]


def test_freeze_timestamps_extra_stacks(settings, tmp_path):
    settings.PG_BASELINE = {
        "BASELINE_DIR": str(tmp_path),
        "FREEZE_TIMESTAMPS_EXTRA": [("audit_log", ["created", "updated"])],
    }
    cfg = get_config()
    assert ("django_migrations", ["applied"]) in cfg.freeze_timestamps
    assert ("audit_log", ["created", "updated"]) in cfg.freeze_timestamps


def test_freeze_timestamps_replaces_when_given(settings, tmp_path):
    settings.PG_BASELINE = {
        "BASELINE_DIR": str(tmp_path),
        "FREEZE_TIMESTAMPS": [("foo", ["ts"])],
    }
    cfg = get_config()
    assert cfg.freeze_timestamps == [("foo", ["ts"])]


def test_sql_and_meta_paths(tmp_path):
    cfg = BaselineConfig(baseline_dir=tmp_path)
    assert cfg.sql_path == tmp_path / "baseline.sql"
    assert cfg.meta_path == tmp_path / "baseline.meta.json"


def test_defaults_are_not_mutated_across_calls(settings, tmp_path):
    settings.PG_BASELINE = {
        "BASELINE_DIR": str(tmp_path),
        "PG_DUMP_EXTRA_EXCLUDE_TABLE_DATA": ["x"],
    }
    cfg1 = get_config()
    cfg1.pg_dump_extra_args.append("--mutation")

    settings.PG_BASELINE = {"BASELINE_DIR": str(tmp_path)}
    cfg2 = get_config()
    assert "--mutation" not in cfg2.pg_dump_extra_args
    assert conf_module.DEFAULT_PG_DUMP_EXTRA_ARGS == DEFAULT_PG_DUMP_EXTRA_ARGS
