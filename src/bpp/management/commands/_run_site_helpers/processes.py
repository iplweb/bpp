"""Spawn / wait / terminate dla runserver i celery worker subprocesses."""

from __future__ import annotations

import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def find_free_port() -> int:
    """Pyta OS o wolny TCP port. Zwraca natychmiast (port może wciąż być wolny)."""
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_listen(
    host: str,
    port: int,
    *,
    timeout: float = 60.0,
    poll_interval: float = 0.1,
) -> bool:
    """Czeka aż ``host:port`` zacznie akceptować TCP — zwraca True/False."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(poll_interval)
    return False


def wait_for_http(
    url: str,
    *,
    timeout: float = 60.0,
    poll_interval: float = 0.2,
    accept_below_status: int = 500,
) -> bool:
    """Czeka aż ``url`` odpowie statusem HTTP < ``accept_below_status``.

    Mocniejszy gate niż ``wait_for_listen``: TCP accept zachodzi w momencie
    ``bind()+listen()`` runservera — *zanim* Django dokończy ładowanie
    URLConf/middleware. Pierwszy żywy request wymusza dopiero to ładowanie
    (lazy URL resolver), więc gdy otworzymy przeglądarkę zaraz po TCP-up,
    Safari trafia w stronę-w-rozruchu i potrafi zacachować błąd.

    Probe HTTP-em najpierw "rozgrzewa" Django (przejście przez handler
    wymusza zaimportowanie URLConf), potem otwieramy browser. Każdy status
    < 500 (200, 301, 302, 404) traktujemy jako sygnał gotowości — Django
    odpowiedział, a o to chodzi. 5xx sugeruje że apka wstała ale crashuje
    (np. brak migracji) i czekamy dalej do timeout-u.
    """
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status < accept_below_status:
                    return True
        except urllib.error.HTTPError as exc:
            # Django odpowiedział, ale 4xx/5xx. 4xx = ready (np. 404 pod
            # nieznanym URL — routing działa). 5xx = nie ready, retry.
            if exc.code < accept_below_status:
                return True
        except (urllib.error.URLError, OSError):
            # Connection refused / DNS / timeout — retry.
            pass
        time.sleep(poll_interval)
    return False


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
