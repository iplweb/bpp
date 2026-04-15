"""Fail loudly when the baseline dump has drifted too far from disk.

The CI workflow runs:

    uv run python baseline/check_freshness.py --max-delta 50

If the number of migrations on disk that postdate the baseline exceeds
``--max-delta`` for any app, exit 1. Developers are then expected to
run ``make rebuild-baseline`` and commit the refreshed dump.

The check is per-app: a 60-migration delta on a small app is just as
loud as a 60-migration delta on bpp. Pick the strictest rule.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
META_PATH = Path(__file__).resolve().parent / "baseline.meta.json"


def _setup_django() -> None:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
    import django

    django.setup()


def collect_disk_migrations() -> dict[str, list[str]]:
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(connection=None, ignore_no_migrations=True)
    by_app: dict[str, list[str]] = {}
    for app_label, name in loader.disk_migrations:
        by_app.setdefault(app_label, []).append(name)
    for names in by_app.values():
        names.sort()
    return by_app


def deltas(disk: dict[str, list[str]], baseline_last: dict[str, str]) -> dict[str, int]:
    """For each app, count migrations on disk strictly newer than baseline.

    A new app that didn't exist when the baseline was generated reports
    its full migration count. An app deleted since the baseline reports 0.
    """
    out: dict[str, int] = {}
    for app, names in disk.items():
        last = baseline_last.get(app)
        if last is None:
            out[app] = len(names)
        else:
            out[app] = sum(1 for n in names if n > last)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max-delta",
        type=int,
        default=50,
        help="Fail when any app has more than this many new migrations "
        "since the baseline was generated.",
    )
    args = parser.parse_args()

    if not META_PATH.exists():
        print(
            f"baseline.meta.json not found at {META_PATH}. "
            "Run `make rebuild-baseline` first.",
            file=sys.stderr,
        )
        return 1

    meta = json.loads(META_PATH.read_text())
    baseline_last: dict[str, str] = meta.get("last_migration", {})

    _setup_django()
    disk = collect_disk_migrations()
    delta_per_app = deltas(disk, baseline_last)

    over = {a: d for a, d in delta_per_app.items() if d > args.max_delta}
    print(
        f"baseline git_sha    = {meta.get('git_sha')}\n"
        f"max-delta threshold = {args.max_delta}\n"
    )
    if not over:
        worst = max(delta_per_app.values(), default=0)
        worst_app = max(delta_per_app, key=delta_per_app.get, default="(none)")
        print(f"OK — largest delta is {worst} migrations in app '{worst_app}'.")
        return 0

    print("STALE — the following apps have too many new migrations:")
    for app, n in sorted(over.items(), key=lambda kv: -kv[1]):
        print(f"  {app}: +{n} new migrations since baseline")
    print(
        "\nRun `make rebuild-baseline`, commit the refreshed "
        "baseline/baseline.sql + baseline.meta.json, push."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
