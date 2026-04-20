"""Local fixtures for django_pg_baseline tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_baseline_dir(tmp_path: Path) -> Path:
    d = tmp_path / "baseline"
    d.mkdir()
    return d


@pytest.fixture
def fake_sql_file(tmp_baseline_dir: Path) -> Path:
    path = tmp_baseline_dir / "baseline.sql"
    path.write_text("-- fake baseline\n")
    return path


@pytest.fixture
def fake_meta_dict() -> dict:
    return {
        "git_sha": "deadbeef",
        "postgres_version": "PostgreSQL 16.0",
        "last_migration": {
            "bpp": "0500_something",
            "auth": "0012_alter_user",
        },
    }


@pytest.fixture
def fake_meta_file(tmp_baseline_dir: Path, fake_meta_dict: dict) -> Path:
    path = tmp_baseline_dir / "baseline.meta.json"
    path.write_text(json.dumps(fake_meta_dict, indent=2, sort_keys=True) + "\n")
    return path


@pytest.fixture
def pg_baseline_settings(settings, tmp_baseline_dir: Path):
    settings.PG_BASELINE = {"BASELINE_DIR": str(tmp_baseline_dir)}
    return settings
