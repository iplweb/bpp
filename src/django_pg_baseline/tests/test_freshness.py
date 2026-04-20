"""Unit tests for django_pg_baseline.freshness."""

from __future__ import annotations

import json

import pytest

from django_pg_baseline import freshness as freshness_module
from django_pg_baseline.freshness import (
    FreshnessReport,
    check_freshness,
    collect_disk_migrations,
    compute_deltas,
)


def test_compute_deltas_new_app_counts_all():
    disk = {"newapp": ["0001_initial", "0002_add"]}
    baseline = {}
    assert compute_deltas(disk, baseline) == {"newapp": 2}


def test_compute_deltas_partial_delta():
    disk = {
        "bpp": ["0001_initial", "0002_x", "0003_y", "0004_z"],
    }
    baseline = {"bpp": "0002_x"}
    assert compute_deltas(disk, baseline) == {"bpp": 2}


def test_compute_deltas_no_new_migrations():
    disk = {"bpp": ["0001_initial", "0002_x"]}
    baseline = {"bpp": "0002_x"}
    assert compute_deltas(disk, baseline) == {"bpp": 0}


def test_compute_deltas_baseline_newer_than_disk():
    disk = {"bpp": ["0001_initial"]}
    baseline = {"bpp": "0009_future"}
    assert compute_deltas(disk, baseline) == {"bpp": 0}


def test_check_freshness_missing_meta_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="baseline.meta.json not found"):
        check_freshness(10, tmp_path / "missing.json")


def test_check_freshness_ok(tmp_path, monkeypatch):
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "git_sha": "abc123",
                "last_migration": {"bpp": "0002_x"},
            }
        )
    )
    monkeypatch.setattr(
        freshness_module,
        "collect_disk_migrations",
        lambda: {"bpp": ["0001_initial", "0002_x", "0003_y"]},
    )

    report = check_freshness(10, meta_path)
    assert isinstance(report, FreshnessReport)
    assert report.ok is True
    assert report.over == {}
    assert report.deltas == {"bpp": 1}
    assert report.worst_app == "bpp"
    assert report.worst_delta == 1
    assert report.git_sha == "abc123"
    assert report.max_delta == 10
    assert report.meta["git_sha"] == "abc123"


def test_check_freshness_stale(tmp_path, monkeypatch):
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(
        json.dumps({"git_sha": "abc", "last_migration": {"bpp": "0001_initial"}})
    )
    monkeypatch.setattr(
        freshness_module,
        "collect_disk_migrations",
        lambda: {
            "bpp": [f"{i:04d}_x" for i in range(1, 20)],
            "auth": ["0001_initial", "0002_x"],
        },
    )

    report = check_freshness(5, meta_path)
    assert report.ok is False
    assert "bpp" in report.over
    assert report.over["bpp"] == 19
    assert report.worst_app == "bpp"
    assert report.worst_delta == 19
    # auth has 2 new migrations, under threshold
    assert "auth" not in report.over


def test_check_freshness_empty_meta_all_count_as_delta(tmp_path, monkeypatch):
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps({"last_migration": {}}))
    monkeypatch.setattr(
        freshness_module,
        "collect_disk_migrations",
        lambda: {"bpp": ["0001", "0002", "0003"]},
    )
    report = check_freshness(100, meta_path)
    assert report.deltas == {"bpp": 3}
    assert report.git_sha is None


def test_collect_disk_migrations_groups_and_sorts(monkeypatch):
    class FakeLoader:
        def __init__(self, connection=None, ignore_no_migrations=False):
            pass

        disk_migrations = [
            ("bpp", "0002_x"),
            ("bpp", "0001_initial"),
            ("auth", "0001_initial"),
        ]

    import django.db.migrations.loader as loader_mod

    monkeypatch.setattr(loader_mod, "MigrationLoader", FakeLoader)

    result = collect_disk_migrations()
    assert result == {
        "bpp": ["0001_initial", "0002_x"],
        "auth": ["0001_initial"],
    }
