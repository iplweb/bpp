"""Loading a baseline pg_dump into a Postgres database.

This module is intentionally Django-free at import time so it can run
from the ``_create_test_db`` monkey patch before ``django.setup()``
completes. stdlib only — shells out to ``psql``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


def baseline_needed(cursor) -> bool:
    """Return True when the DB has no ``django_migrations`` table.

    Precise signal of "completely empty Django database" — Django creates
    ``django_migrations`` as the very first step of any migrate, so even
    a partially-migrated DB will have it.
    """
    cursor.execute("SELECT to_regclass('public.django_migrations')")
    row = cursor.fetchone()
    return row is None or row[0] is None


def load_baseline(
    dsn: Mapping[str, object],
    dump_path: Path,
) -> None:
    """Load ``dump_path`` into the database described by ``dsn``.

    ``dsn`` is the dict from ``connection.settings_dict`` (or an
    equivalent with NAME / USER / PASSWORD / HOST / PORT keys). The
    dump contains CREATE EXTENSION, SET, COPY FROM stdin and similar
    statements that the Django backend cannot parse; ``psql`` handles
    them natively. Wrapped in a single transaction with ON_ERROR_STOP.
    """
    dump_path = Path(dump_path)
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
