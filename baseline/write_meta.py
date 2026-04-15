"""Generate ``baseline/baseline.meta.json`` for the current source tree.

Walks every Django app's ``migrations/`` directory on disk and records
the highest-numbered (lexicographically last) migration name per app.
That metadata is the source of truth for ``check_freshness.py`` and
becomes a sidecar to the SQL dump in git.

Run via:

    uv run python baseline/write_meta.py

The script needs Django to be importable but does NOT touch the
database — it only walks ``MigrationLoader.disk_migrations``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
META_PATH = Path(__file__).resolve().parent / "baseline.meta.json"


def _setup_django() -> None:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
    import django

    django.setup()


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
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
    except Exception:  # pragma: no cover — running without DB
        return None


def collect_last_migrations() -> dict[str, str]:
    """Return ``{app_label: last_migration_name}`` from disk."""
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(connection=None, ignore_no_migrations=True)
    by_app: dict[str, list[str]] = {}
    for app_label, name in loader.disk_migrations:
        by_app.setdefault(app_label, []).append(name)
    return {app: max(names) for app, names in sorted(by_app.items())}


def main() -> int:
    _setup_django()
    meta = {
        "git_sha": _git_sha(),
        "postgres_version": _postgres_version(),
        "last_migration": collect_last_migrations(),
    }
    META_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(f"[baseline] wrote {META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
