"""Detekcja formatu dumpu i budowa komendy restore."""

from __future__ import annotations

import gzip
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# pg_restore -j N wymaga seekable pliku — nie potrafi parallel-restore z pipe/
# stdin (zob. dokumentacja pg_restore: "input must be a regular file or
# directory"). Stąd dla pgdump-ów: docker cp do /tmp/ → exec → cleanup.
_DUMP_IN_CONTAINER = "/tmp/bpp_restore.pgdump"

# Cap na jobs: powyżej ~8 dla typowego dev-laptopa zysk z parallelism znika
# (bottleneck przesuwa się na WAL/dysk), a koszt context-switch rośnie.
_DEFAULT_JOBS_CAP = 8


def _resolve_jobs() -> int:
    """Liczba workerów dla ``pg_restore -j``.

    Override przez ``BPP_RESTORE_JOBS`` (np. ``=1`` żeby wyłączyć paralelizm
    przy debugowaniu); inaczej ``min(8, cpu_count())``.
    """
    override = os.environ.get("BPP_RESTORE_JOBS", "").strip()
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            logger.warning(
                "BPP_RESTORE_JOBS=%r nie jest liczbą całkowitą — ignoruję",
                override,
            )
    return min(_DEFAULT_JOBS_CAP, os.cpu_count() or 4)


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
    dump_in_container: str | None = None,
    jobs: int = 1,
) -> tuple[list[str], bool]:
    """Buduje komendę docker exec do restore.

    Args:
        format: 'sql' / 'sql.gz' / 'pgdump'.
        container_id: ID/name kontenera PG.
        db_user, db_name: parametry połączenia.
        dump_in_container: ścieżka do pliku dumpu *wewnątrz* kontenera —
            wymagana dla ``pgdump`` (pg_restore z ``-j`` nie czyta z stdin,
            potrzebuje seekable pliku).
        jobs: liczba równoległych workerów dla ``pg_restore -j N``. Gdy
            ``jobs <= 1``, ``-j`` jest pomijane.

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
        if dump_in_container is None:
            raise ValueError(
                "Format pgdump wymaga dump_in_container "
                "(pg_restore -j nie obsługuje pipe ze stdin)"
            )
        # Brak --clean / --if-exists: zakładamy pustą bazę (caller suppressuje
        # baseline). --clean by tu walczył z FK cascade (constraint dependencies
        # na pbn_api_publication_pkey, bpp_autor_pkey itp.).
        # --no-owner: ignoruje ALTER OWNER z dump-a (user "bpp" może nie
        # mieć permission do ról istniejących na production source DB).
        # --exit-on-error: pierwszy błąd kończy proces.
        cmd = [
            "docker",
            "exec",
            container_id,
            "pg_restore",
            "--no-owner",
            "--exit-on-error",
            "-U",
            db_user,
            "-d",
            db_name,
        ]
        if jobs > 1:
            cmd += ["-j", str(jobs)]
        cmd.append(dump_in_container)
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

    if fmt == "pgdump":
        _restore_pgdump_parallel(dump_path, container_id, db_user, db_name)
        return

    cmd, needs_decompress = build_restore_command(fmt, container_id, db_user, db_name)
    logger.info("Restore: %s (%s) → container %s", dump_path, fmt, container_id)

    if needs_decompress:
        with gzip.open(dump_path, "rb") as src:
            subprocess.run(cmd, stdin=src, check=True)
    else:
        with open(dump_path, "rb") as src:
            subprocess.run(cmd, stdin=src, check=True)
    logger.info("Restore: ukończony")


def _restore_pgdump_parallel(
    dump_path: Path,
    container_id: str,
    db_user: str,
    db_name: str,
) -> None:
    """pg_restore -j N: kopiuje dump do kontenera, restore-uje, sprząta.

    pg_restore nie potrafi parallel-restore z pipe (potrzebuje seek), więc
    plik musi trafić do file-systemu kontenera. ``docker cp`` jest tu
    najprostszą metodą — alternatywą byłby mount wolumenu, ale kontener
    działa już od momentu startu testcontainers/run_site i nie da się
    do-mountować na żywo.
    """
    jobs = _resolve_jobs()
    logger.info(
        "Restore: %s (pgdump, -j %d) → container %s",
        dump_path,
        jobs,
        container_id,
    )
    subprocess.run(
        [
            "docker",
            "cp",
            str(dump_path),
            f"{container_id}:{_DUMP_IN_CONTAINER}",
        ],
        check=True,
    )
    try:
        cmd, _ = build_restore_command(
            "pgdump",
            container_id,
            db_user,
            db_name,
            dump_in_container=_DUMP_IN_CONTAINER,
            jobs=jobs,
        )
        subprocess.run(cmd, check=True)
    finally:
        # Cleanup best-effort: jeśli rm zawiedzie (np. kontener zatrzymany
        # po błędzie restore), zostaje ślad w /tmp wewnątrz kontenera —
        # nieszkodliwy, znika z kontenerem. Logujemy z exc_info, nie reraise,
        # żeby nie zamaskować właściwego błędu z pg_restore.
        try:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container_id,
                    "rm",
                    "-f",
                    _DUMP_IN_CONTAINER,
                ],
                check=False,
            )
        except OSError:
            logger.warning(
                "Nie udało się usunąć tmp dump %s w kontenerze %s",
                _DUMP_IN_CONTAINER,
                container_id,
                exc_info=True,
            )
    logger.info("Restore: ukończony")
