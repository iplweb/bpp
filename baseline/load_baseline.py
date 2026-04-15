"""Helpers for loading the baseline ``pg_dump`` into an empty database.

This module is intentionally Django-free at import time so it can be
imported from ``conftest.py`` before ``django.setup()``. It only uses
the standard library and shells out to ``psql`` via ``subprocess``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

BASELINE_DIR = Path(__file__).resolve().parent
BASELINE_SQL = BASELINE_DIR / "baseline.sql"
BASELINE_META = BASELINE_DIR / "baseline.meta.json"


def baseline_needed(cursor) -> bool:
    """Return True when the database has no ``django_migrations`` table.

    This is the precise signal of "completely empty Django database".
    Existing databases — even partially migrated ones — always have
    this table (Django creates it as the very first migration step).
    """
    cursor.execute("SELECT to_regclass('public.django_migrations')")
    row = cursor.fetchone()
    return row is None or row[0] is None


def load_baseline(
    dsn: Mapping[str, object],
    dump_path: Path = BASELINE_SQL,
) -> None:
    """Load ``dump_path`` into the database described by ``dsn``.

    ``dsn`` is the dict returned by Django's ``connection.settings_dict``
    (or a hand-rolled equivalent with NAME / USER / PASSWORD / HOST /
    PORT keys). We do NOT use a Django cursor — the dump contains
    ``CREATE EXTENSION``, ``SET``, ``COPY FROM stdin`` and other
    statements that the Django backend cannot parse. ``psql`` handles
    them natively.

    The load is wrapped in a single transaction with ``ON_ERROR_STOP``
    so a partial failure rolls back cleanly and the next run can retry.
    """
    if not dump_path.exists():
        raise FileNotFoundError(f"Baseline dump not found: {dump_path}")

    env = os.environ.copy()
    env["PGHOST"] = str(dsn.get("HOST") or "localhost")
    env["PGPORT"] = str(dsn.get("PORT") or 5432)
    env["PGUSER"] = str(dsn.get("USER") or "")
    env["PGPASSWORD"] = str(dsn.get("PASSWORD") or "")
    db_name = str(dsn["NAME"])

    cmd = [
        "psql",
        "-d",
        db_name,
        "-v",
        "ON_ERROR_STOP=1",
        "--single-transaction",
        "--quiet",
        "-f",
        str(dump_path),
    ]
    print(
        f"[baseline] loading {dump_path.name} into {db_name} ...",
        file=sys.stderr,
    )
    subprocess.run(cmd, env=env, check=True)
    print("[baseline] load complete", file=sys.stderr)
