"""Build ``baseline.meta.json`` from the current source tree."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _postgres_version() -> str | None:
    from django.db import connection

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"[baseline] could not read postgres version: {exc}")
        return None


def collect_last_migrations() -> dict[str, str]:
    """Return ``{app_label: last_migration_name}`` from disk."""
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(connection=None, ignore_no_migrations=True)
    by_app: dict[str, list[str]] = {}
    for app_label, name in loader.disk_migrations:
        by_app.setdefault(app_label, []).append(name)
    return {app: max(names) for app, names in sorted(by_app.items())}


def write_meta(meta_path: Path) -> None:
    meta = {
        "git_sha": _git_sha(),
        "postgres_version": _postgres_version(),
        "last_migration": collect_last_migrations(),
    }
    meta_path = Path(meta_path)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(f"[baseline] wrote {meta_path}")
