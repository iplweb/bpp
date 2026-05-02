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


def spawn_runserver(port: int, env: dict[str, str]) -> subprocess.Popen:
    """Spawn `manage.py runserver 127.0.0.1:port` w foreground.

    Caller czeka via `proc.wait()`. NIE przekazujemy stdin.
    """
    src = _src_dir()
    cmd = [
        _python_executable(),
        str(src / "manage.py"),
        "runserver",
        f"127.0.0.1:{port}",
    ]
    logger.info("Spawn runserver: %s", " ".join(cmd))
    return subprocess.Popen(cmd, env=env, cwd=str(src))


def spawn_celery(env: dict[str, str]) -> subprocess.Popen:
    """Spawn celery worker w background (stdout/stderr → DEVNULL)."""
    src = _src_dir()
    cmd = [
        _python_executable(),
        "-m",
        "celery",
        "-A",
        "django_bpp.tasks",
        "worker",
        "-l",
        "info",
    ]
    logger.info("Spawn celery: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        env=env,
        cwd=str(src),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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
