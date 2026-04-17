"""Orchestrate baseline regeneration using testcontainers.

This replaces the Makefile target that used to spin up an isolated
Postgres via ``docker compose -f docker-compose.baseline.yml``.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .conf import BaselineConfig
from .writer import write_meta


def _freeze_timestamps(alias: str, config: BaselineConfig) -> None:
    from django.db import connections

    value = config.freeze_timestamp_value
    with connections[alias].cursor() as cur:
        for table, columns in config.freeze_timestamps:
            cur.execute(
                "SELECT to_regclass(%s)",
                [f"public.{table}"],
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                continue
            set_clause = ", ".join(f"{col} = %s::timestamptz" for col in columns)
            cur.execute(
                f"UPDATE {table} SET {set_clause}",
                [value] * len(columns),
            )


def _run_pg_dump(dsn: dict, config: BaselineConfig) -> None:
    cmd = [
        "pg_dump",
        "-h",
        str(dsn["HOST"]),
        "-p",
        str(dsn["PORT"]),
        "-U",
        str(dsn["USER"]),
        "-d",
        str(dsn["NAME"]),
        "--format=plain",
        "--encoding=UTF8",
        *config.pg_dump_extra_args,
    ]
    env = {"PGPASSWORD": str(dsn.get("PASSWORD") or "")}
    import os

    full_env = {**os.environ, **env}
    config.sql_path.parent.mkdir(parents=True, exist_ok=True)
    with config.sql_path.open("wb") as fh:
        subprocess.run(cmd, env=full_env, check=True, stdout=fh)


def _strip_restrict_tokens(sql_path: Path) -> None:
    """Remove non-deterministic ``\\restrict`` / ``\\unrestrict`` lines.

    Newer pg_dump emits these psql meta-commands with random tokens,
    which break determinism. The lines are harmless to strip.
    """
    pattern = re.compile(r"^\\(un)?restrict ")
    text = sql_path.read_text(encoding="utf-8")
    kept = [line for line in text.splitlines(keepends=True) if not pattern.match(line)]
    sql_path.write_text("".join(kept), encoding="utf-8")


def _register_temp_alias(
    host: str, port: int, user: str, password: str, db: str
) -> str:
    from django.db import connections

    alias = "pg_baseline_rebuild"
    connections.databases[alias] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": str(port),
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": False,
        "OPTIONS": {},
        "TIME_ZONE": None,
        "TEST": {},
    }
    connections[alias].ensure_connection()
    return alias


def rebuild_baseline(config: BaselineConfig) -> None:
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError as exc:
        raise RuntimeError(
            "testcontainers is required for baseline_rebuild. "
            "Install with: uv sync --extra baseline-rebuild"
        ) from exc

    from django.core.management import call_command
    from django.db import connections

    container = PostgresContainer(
        image=config.rebuild_image,
        username="bpp",
        password="password",
        dbname="bpp_baseline",
        driver=None,
    )
    with container as pg:
        host = pg.get_container_host_ip()
        port = int(pg.get_exposed_port(5432))
        alias = _register_temp_alias(host, port, "bpp", "password", "bpp_baseline")

        try:
            call_command("migrate", database=alias, interactive=False, verbosity=1)
            _freeze_timestamps(alias, config)
            connections[alias].close()

            dsn = {
                "HOST": host,
                "PORT": port,
                "USER": "bpp",
                "PASSWORD": "password",
                "NAME": "bpp_baseline",
            }
            _run_pg_dump(dsn, config)
            _strip_restrict_tokens(config.sql_path)
            write_meta(config.meta_path)
        finally:
            try:
                connections[alias].close()
            except Exception as exc:  # noqa: BLE001
                print(f"[baseline] warning: could not close alias: {exc}")
            connections.databases.pop(alias, None)
