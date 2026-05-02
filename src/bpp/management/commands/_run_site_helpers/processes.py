"""Spawn / wait / terminate dla runserver i celery worker subprocesses."""

from __future__ import annotations

import logging
import socket
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def find_free_port() -> int:
    """Pyta OS o wolny TCP port. Zwraca natychmiast (port może wciąż być wolny)."""
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _src_dir() -> Path:
    """Zwraca katalog `src/` (parent of bpp app)."""
    # __file__ = src/bpp/management/commands/_run_site_helpers/processes.py
    # parents[4] = src/
    return Path(__file__).resolve().parents[4]


def _python_executable() -> str:
    """Path do Python interpreter — używa sys.executable, więc subprocess
    odziedziczą venv (uv run zachowany)."""
    return sys.executable


def _env_with_unbuffered(env: dict[str, str]) -> dict[str, str]:
    """Wymuś line-buffering na child Pythonie — bez tego pipe-owany stdout
    jest block-buffered i logi nie pojawiają się dopóki bufor (~4 KB) się
    nie zapełni. Dla multipleksera to katastrofa — kolejność linii
    runserver/celery byłaby losowa."""
    out = dict(env)
    out.setdefault("PYTHONUNBUFFERED", "1")
    return out


def spawn_runserver(port: int, env: dict[str, str]) -> subprocess.Popen:
    """Spawn `manage.py runserver 127.0.0.1:port` z stdout/stderr → PIPE.

    Caller czyta stdout (multiplexer), ``proc.wait()`` blokuje do końca.
    NIE przekazujemy stdin. Reload zostaje włączony (default Django) — z
    autoreload child dziedziczy ten sam pipe, a ponieważ nasze linie logów
    nie przekraczają ``PIPE_BUF`` (4 KB), POSIX gwarantuje atomic writes
    przez co dwa procesy nie sklejają sobie linii.
    """
    src = _src_dir()
    cmd = [
        _python_executable(),
        str(src / "manage.py"),
        "runserver",
        f"127.0.0.1:{port}",
    ]
    logger.info("Spawn runserver: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        env=_env_with_unbuffered(env),
        cwd=str(src),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def spawn_celery(env: dict[str, str]) -> subprocess.Popen:
    """Spawn celery worker z stdout/stderr → PIPE (czytane przez multiplexer).

    Używamy ``--pool=solo`` żeby uniknąć segfaultów przy fork() na macOS
    (psycopg2/numpy/lxml + Apple's malloc-after-fork checks). Dla dev
    pojedynczy worker w jednym wątku jest wystarczający.
    """
    src = _src_dir()
    cmd = [
        _python_executable(),
        "-m",
        "celery",
        "-A",
        "django_bpp.celery_tasks",
        "worker",
        "--pool=solo",
        "-l",
        "info",
    ]
    logger.info("Spawn celery: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        env=_env_with_unbuffered(env),
        cwd=str(src),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def spawn_pg_logs(container_id: str) -> subprocess.Popen:
    """Spawn ``docker logs -f --tail 0 <id>`` żeby strumieniować logi PG.

    ``--tail 0`` żeby nie wypluć całej historii startu kontenera (testcontainers
    już to przed chwilą zalogował przy starcie). ``-f`` (follow) blokuje aż
    ktoś zabije proces — robi to caller w cleanup-ie przez ``wait_terminate``.
    """
    cmd = ["docker", "logs", "-f", "--tail", "0", container_id]
    logger.info("Spawn pg-logs: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def wait_terminate(proc: subprocess.Popen, timeout: float = 5.0) -> None:
    """Wyślij SIGTERM, poczekaj timeout, jeśli nie wyszedł — SIGKILL."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("Process %s did not terminate, killing", proc.pid)
        proc.kill()
        proc.wait(timeout=2.0)


def run_subprocess_blocking(
    cmd: list[str],
    env: dict[str, str],
    cwd: str | None = None,
) -> int:
    """Uruchom subprocess i czekaj. Zwraca returncode."""
    logger.info("Subprocess: %s", " ".join(cmd))
    return subprocess.run(cmd, env=env, cwd=cwd).returncode
