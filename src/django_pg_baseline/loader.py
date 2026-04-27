"""Loading a baseline pg_dump into a Postgres database.

This module is intentionally Django-free at import time so it can run
from the ``_create_test_db`` monkey patch before ``django.setup()``
completes. stdlib only — shells out to ``psql``.

When tests run against a Postgres testcontainer started by
``testcontainers_bpp``, the baseline is loaded **inside** the container
at startup (via Postgres' ``/docker-entrypoint-initdb.d/`` mechanism)
and ``test_bpp`` is created with ``CREATE DATABASE ... WITH TEMPLATE
bpp``, so this module's host ``psql`` path is **not** invoked. It still
runs for the ``baseline_load`` management command and for the
``--no-testcontainers`` test scenario, where a host ``psql`` is
expected to be available.
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
    # stdout captured to silence the wall of `setval`/`set_config` result
    # rows the dump produces; stderr stays inherited so real psql errors
    # / NOTICEs still reach the user. On failure we re-emit the captured
    # stdout to stderr so partial output is not lost.
    result = subprocess.run(
        cmd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout
        )
    print("[baseline] load complete", file=sys.stderr)
