"""Detekcja formatu dumpu i budowa komendy restore."""

from __future__ import annotations

import gzip
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_dump_format(path: Path) -> str | None:
    """Zwraca 'sql' / 'sql.gz' / 'pgdump' lub None.

    Detekcja po extension (case-insensitive). Treść pliku NIE jest
    inspekcjonowana — kompromis simplicity vs. correctness OK dla dev tool.
    """
    name = path.name.lower()
    if name.endswith(".sql.gz"):
        return "sql.gz"
    if name.endswith(".sql"):
        return "sql"
    if name.endswith(".dump") or name.endswith(".pgdump") or name.endswith(".pg_dump"):
        return "pgdump"
    return None


def build_restore_command(
    format: str,
    container_id: str,
    db_user: str = "bpp",
    db_name: str = "bpp",
) -> tuple[list[str], bool]:
    """Buduje komendę docker exec do restore.

    Args:
        format: 'sql' / 'sql.gz' / 'pgdump'.
        container_id: ID/name kontenera PG.
        db_user, db_name: parametry połączenia.

    Returns:
        (cmd, needs_decompression) — cmd to lista argów do subprocess,
        decompress=True oznacza że caller musi wgzipsknąć stdin (sql.gz).
    """
    if format in ("sql", "sql.gz"):
        cmd = [
            "docker",
            "exec",
            "-i",
            container_id,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            db_user,
            "-d",
            db_name,
        ]
        return cmd, format == "sql.gz"
    if format == "pgdump":
        # Brak --clean / --if-exists: zakładamy pustą bazę (caller suppressuje
        # baseline). --clean by tu walczył z FK cascade (constraint dependencies
        # na pbn_api_publication_pkey, bpp_autor_pkey itp.).
        # --no-owner: ignoruje ALTER OWNER z dump-a (user "bpp" może nie
        # mieć permission do ról istniejących na production source DB).
        # --exit-on-error: pierwszy błąd kończy proces.
        cmd = [
            "docker",
            "exec",
            "-i",
            container_id,
            "pg_restore",
            "--no-owner",
            "--exit-on-error",
            "-U",
            db_user,
            "-d",
            db_name,
        ]
        return cmd, False
    raise ValueError(f"Nieobsługiwany format: {format!r}")


def restore_dump(
    dump_path: Path,
    container_id: str,
    db_user: str = "bpp",
    db_name: str = "bpp",
) -> None:
    """Wykonuje restore dump-a do kontenera. Rzuca CalledProcessError przy błędzie."""
    fmt = detect_dump_format(dump_path)
    if fmt is None:
        raise ValueError(f"Nieobsługiwany format pliku: {dump_path.name}")

    cmd, needs_decompress = build_restore_command(fmt, container_id, db_user, db_name)
    logger.info("Restore: %s (%s) → container %s", dump_path, fmt, container_id)

    if needs_decompress:
        with gzip.open(dump_path, "rb") as src:
            subprocess.run(cmd, stdin=src, check=True)
    else:
        with open(dump_path, "rb") as src:
            subprocess.run(cmd, stdin=src, check=True)
    logger.info("Restore: ukończony")
