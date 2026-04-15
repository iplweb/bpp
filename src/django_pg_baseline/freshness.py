"""Compute the migration delta between on-disk migrations and the baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FreshnessReport:
    ok: bool
    max_delta: int
    deltas: dict[str, int]
    over: dict[str, int]
    git_sha: str | None
    worst_app: str
    worst_delta: int
    meta: dict = field(default_factory=dict)


def collect_disk_migrations() -> dict[str, list[str]]:
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(connection=None, ignore_no_migrations=True)
    by_app: dict[str, list[str]] = {}
    for app_label, name in loader.disk_migrations:
        by_app.setdefault(app_label, []).append(name)
    for names in by_app.values():
        names.sort()
    return by_app


def compute_deltas(
    disk: dict[str, list[str]],
    baseline_last: dict[str, str],
) -> dict[str, int]:
    out: dict[str, int] = {}
    for app, names in disk.items():
        last = baseline_last.get(app)
        if last is None:
            out[app] = len(names)
        else:
            out[app] = sum(1 for n in names if n > last)
    return out


def check_freshness(max_delta: int, meta_path: Path) -> FreshnessReport:
    meta_path = Path(meta_path)
    if not meta_path.exists():
        raise FileNotFoundError(
            f"baseline.meta.json not found at {meta_path}. Run baseline_rebuild first."
        )
    meta = json.loads(meta_path.read_text())
    baseline_last: dict[str, str] = meta.get("last_migration", {})
    disk = collect_disk_migrations()
    deltas = compute_deltas(disk, baseline_last)
    over = {a: d for a, d in deltas.items() if d > max_delta}
    worst_delta = max(deltas.values(), default=0)
    worst_app = max(deltas, key=deltas.get, default="(none)") if deltas else "(none)"
    return FreshnessReport(
        ok=not over,
        max_delta=max_delta,
        deltas=deltas,
        over=over,
        git_sha=meta.get("git_sha"),
        worst_app=worst_app,
        worst_delta=worst_delta,
        meta=meta,
    )
