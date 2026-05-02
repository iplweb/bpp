# `manage.py run_site` — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jedna komenda Django (`uv run python src/manage.py run_site --from-dump <path>`), która (1) startuje testcontainery PostgreSQL+Redis na losowych portach, (2) odtwarza dump (autodetect formatu) lub baseline jeśli dump nie podany, (3) tworzy superusera `admin/admin`, (4) drukuje banner z URL-ami i otwiera Firefoxa, (5) odpala `runserver` jako subprocess i blokuje. Ctrl-C kończy runserver → testcontainers tear down → koniec procesu.

**Architecture:** Management command orkiestruje. Sam nie używa cached Django connection (settings załadowane przed `handle()`); całą Django-pracę (createsuperuser, runserver) deleguje do subprocesów które dziedziczą wstrzyknięte env-vary i widzą fresh containers. Restore dump robimy przez `docker exec` w PG container — eliminuje wymóg lokalnego psql/pg_restore. Reuse `start_containers()` / `stop_containers()` z `src/testcontainers_bpp/containers.py`.

**Tech stack:** Django 4/5, testcontainers-py, docker-py, pytest, model_bakery.

**Spec:** embedded — sekcja "Design" poniżej.

---

## Design (embedded spec)

### CLI

```
uv run python src/manage.py run_site [OPTIONS]

  --from-dump PATH    Plik do odtworzenia (.sql / .sql.gz / .dump). Default: baseline.
  --with-celery       Dodatkowo odpal celery worker (default: off).
  --no-browser        Nie otwieraj przeglądarki (default: otwiera).
  --port PORT         Port runserver (default: pick free port).
  --reuse             Reuse istniejące kontenery zamiast tworzyć nowe (default: off).
```

### Lifecycle

1. **Pre-flight** — `_check_docker_daemon()`. Sprawdź że `--from-dump` istnieje (jeśli podany).
2. **Start containers** — `start_containers(reuse=...)` z `testcontainers_bpp.containers`. Default: ephemeral (Ryuk reapuje na exit). Z `--reuse`: persistent named containers.
3. **Restore** — jeśli `--from-dump`: ładuj dump przez `docker exec`. Bez `--from-dump`: baseline jest już załadowany przez init scripts kontenera (bo `start_containers` mountuje go do `/docker-entrypoint-initdb.d/`).
4. **Inject env vars** — przed spawn-em jakiegokolwiek subprocess-u Django.
5. **Migrate** — `python src/manage.py migrate --noinput` (subprocess). Niezbędne na wypadek dumpa starszej wersji niż code.
6. **Create superuser** — `python src/manage.py createsuperuser --noinput` (subprocess) z env varami `DJANGO_SUPERUSER_USERNAME=admin`, `DJANGO_SUPERUSER_PASSWORD=admin`, `DJANGO_SUPERUSER_EMAIL=admin@example.com`. Idempotent — przy konflikcie loguje warning i kontynuuje.
7. **Banner** — wypisz porty/URL-e w czytelnej formie.
8. **Open browser** — `webbrowser.open(f"http://localhost:{port}/admin/")` (default, chyba że `--no-browser`).
9. **Spawn celery (opcjonalnie)** — `--with-celery` → `celery -A django_bpp.tasks worker -l info` jako subprocess background.
10. **Spawn runserver** — `python src/manage.py runserver 127.0.0.1:<port>` jako subprocess, block until exit.
11. **Cleanup w `finally`** — terminate celery worker, `stop_containers(...)`. Reuse=True pomija stop.

### Env vars wstrzykiwane

Po `start_containers`:

```python
os.environ["DJANGO_BPP_DB_HOST"] = c.pg_host
os.environ["DJANGO_BPP_DB_PORT"] = str(c.pg_port)
os.environ["DJANGO_BPP_REDIS_HOST"] = c.redis_host
os.environ["DJANGO_BPP_REDIS_PORT"] = str(c.redis_port)
os.environ["DJANGO_BPP_SKIP_DOTENV"] = "1"  # żeby .env nie nadpisał
os.environ["DJANGO_SUPERUSER_USERNAME"] = "admin"
os.environ["DJANGO_SUPERUSER_PASSWORD"] = "admin"
os.environ["DJANGO_SUPERUSER_EMAIL"] = "admin@example.com"
```

### Dump autodetect

| Extension | Operacja |
|-----------|----------|
| `.sql` | `cat dump.sql \| docker exec -i $C psql -U bpp -d bpp` |
| `.sql.gz` | `gunzip -c dump.sql.gz \| docker exec -i $C psql -U bpp -d bpp` |
| `.dump` (lub `.pgdump`) | `cat dump.dump \| docker exec -i $C pg_restore --clean --if-exists -U bpp -d bpp` |
| inne | error: "Nieobsługiwany format. Użyj .sql / .sql.gz / .dump" |

Restore wykonujemy przez `subprocess.run(...)` z `stdin=open(file, "rb")`.

### Wybór wolnego portu

```python
import socket
def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]
```

### Banner format

```
╔══════════════════════════════════════════════════════════╗
║  BPP run-site — stack uruchomiony                       ║
╠══════════════════════════════════════════════════════════╣
║  Appserver:  http://localhost:54321/                     ║
║  Admin:      http://localhost:54321/admin/               ║
║              login: admin   hasło: admin                 ║
║                                                          ║
║  PostgreSQL: 127.0.0.1:54322 (bpp/password)             ║
║  Redis:      127.0.0.1:54323                             ║
║                                                          ║
║  Celery:     [running] | [disabled]                      ║
║  Dump:       /path/to/dump.sql.gz | [baseline]           ║
╠══════════════════════════════════════════════════════════╣
║  Ctrl-C zakończy serwer i sprzątnie kontenery.          ║
╚══════════════════════════════════════════════════════════╝
```

(W kodzie banner jako f-string z `{value:<43}`. Nie używamy `rich` — żeby uniknąć dependency-creep dla dev-toolsa.)

### File structure

- **Create:** `src/bpp/management/commands/run_site.py` — Command class.
- **Create:** `src/bpp/management/commands/_run_site_helpers/__init__.py`
- **Create:** `src/bpp/management/commands/_run_site_helpers/restore.py` — funkcje `restore_dump`, `detect_dump_format`.
- **Create:** `src/bpp/management/commands/_run_site_helpers/banner.py` — funkcja `print_banner`.
- **Create:** `src/bpp/management/commands/_run_site_helpers/processes.py` — funkcje `spawn_runserver`, `spawn_celery_worker`, `wait_terminate`.
- **Create:** `src/bpp/tests/test_run_site_helpers.py` — unit testy bez Dockera.
- **Modify:** brak (poza opcjonalnym newsfragment).

---

## Konwencje wykonania

- **Worktree:** `~/Programowanie/bpp-worktrees/run-site-command/`, branch `feature/run-site-command`, base `dev`.
- **Python:** zawsze `uv run`, NIGDY goły `python`.
- **Pytest:** `UV_NO_SYNC=1 uv run --all-extras pytest <target> -n auto 2>&1 | tee /tmp/log.log`. Output zawsze do pliku.
- **Pre-commit:** auto na commit. Nie używać `--all-files`. Fix manualnie jeśli zawiedzie.
- **Max linia:** 88 znaków.
- **Polski w identyfikatorach/komentarzach:** OK.
- **Docker daemon wymagany** — testy oznaczamy `@pytest.mark.skipif(not docker_available())`.

---

## Phase 0: Worktree

### Task 0.1: Utworzenie worktree

- [ ] **Step 1: Sanity check**

```bash
cd /Users/mpasternak/Programowanie/bpp
git status
git fetch origin
git log --oneline -3 dev
```

Expected: `dev` clean (bądź ustaw).

- [ ] **Step 2: Utwórz worktree**

```bash
git worktree add ~/Programowanie/bpp-worktrees/run-site-command -b feature/run-site-command dev
cd ~/Programowanie/bpp-worktrees/run-site-command
```

- [ ] **Step 3: Zainstaluj deps**

```bash
uv sync --all-extras
```

- [ ] **Step 4: Sanity-test istniejące**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/testcontainers_bpp/tests/ -n auto 2>&1 | tee /tmp/runsite-sanity.log | tail -10
```

Expected: zielone — dowód, że testcontainers działa.

---

## Phase 1: Skeleton komendy + arg parsing

### Task 1.1: Stub `run_site` z arg-parsing-iem

**Files:**
- Create: `src/bpp/management/commands/run_site.py`
- Test: `src/bpp/tests/test_run_site_command.py`

- [ ] **Step 1: Failing test — arg parsing**

`src/bpp/tests/test_run_site_command.py`:

```python
"""Testy command-line interface komendy run_site (no Docker required)."""

from io import StringIO

import pytest
from django.core.management import call_command


def test_run_site_help_does_not_crash():
    """Sanity check że komenda jest zarejestrowana."""
    out = StringIO()
    with pytest.raises(SystemExit) as exc_info:
        call_command("run_site", "--help", stdout=out)
    assert exc_info.value.code == 0
    text = out.getvalue()
    assert "--from-dump" in text
    assert "--with-celery" in text
    assert "--no-browser" in text
    assert "--port" in text
    assert "--reuse" in text


def test_run_site_invalid_dump_path_raises(tmp_path):
    """Nieistniejący `--from-dump` rzuca CommandError od razu."""
    from django.core.management.base import CommandError

    nonexistent = tmp_path / "no-such-file.sql"
    with pytest.raises(CommandError, match="nie istnieje"):
        call_command("run_site", "--from-dump", str(nonexistent), "--dry-run")


def test_run_site_unsupported_format_raises(tmp_path):
    """Plik o nieobsługiwanym rozszerzeniu rzuca CommandError."""
    from django.core.management.base import CommandError

    bad = tmp_path / "dump.tar"
    bad.write_text("x")
    with pytest.raises(CommandError, match="format"):
        call_command("run_site", "--from-dump", str(bad), "--dry-run")
```

`--dry-run` wprowadzimy w step 3 — to flaga internal, parsujemy + walidujemy + return early.

- [ ] **Step 2: Run — fail**

```bash
cd ~/Programowanie/bpp-worktrees/run-site-command
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_command.py -n0 2>&1 | tee /tmp/runsite-task1-1-fail.log
```

Expected: `Unknown command: 'run_site'`.

- [ ] **Step 3: Implement skeleton**

`src/bpp/management/commands/run_site.py`:

```python
"""Management command: uruchom dev stack z testcontainerami.

Startuje PG+Redis na losowych portach (testcontainers), odtwarza dump,
tworzy superusera admin/admin, odpala runserver i blokuje. Ctrl-C
zatrzymuje runserver i sprząta kontenery.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


SUPPORTED_EXTENSIONS = {".sql", ".gz", ".dump", ".pgdump"}


class Command(BaseCommand):
    help = (
        "Odpala dev stack BPP: PG+Redis (testcontainers) + runserver. "
        "Opcjonalnie odtwarza dump i odpala celery."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-dump",
            type=str,
            default=None,
            metavar="PATH",
            help="Plik do odtworzenia (.sql / .sql.gz / .dump). "
            "Domyślnie: baseline.sql z obrazu PG.",
        )
        parser.add_argument(
            "--with-celery",
            action="store_true",
            default=False,
            help="Dodatkowo odpal celery worker.",
        )
        parser.add_argument(
            "--no-browser",
            action="store_true",
            default=False,
            help="Nie otwieraj przeglądarki.",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=None,
            help="Port runserver (default: wolny port).",
        )
        parser.add_argument(
            "--reuse",
            action="store_true",
            default=False,
            help="Reuse named containers (BPP_TESTCONTAINERS_REUSE).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Tylko walidacja args + exit (do testów).",
        )

    def handle(self, *args, **opts):
        dump_path = self._validate_dump_arg(opts.get("from_dump"))

        if opts.get("dry_run"):
            self.stdout.write(self.style.SUCCESS("dry-run OK"))
            return

        # Pełne wykonanie — wprowadzane w kolejnych taskach.
        raise CommandError(
            "Pełna implementacja w toku — na razie obsłużone tylko --dry-run "
            "i walidacja args."
        )

    def _validate_dump_arg(self, dump: str | None) -> Path | None:
        if dump is None:
            return None
        path = Path(dump).expanduser().resolve()
        if not path.is_file():
            raise CommandError(f"Plik dump-a nie istnieje: {path}")
        if not _detect_dump_format(path):
            raise CommandError(
                f"Nieobsługiwany format pliku {path.name}. "
                f"Użyj .sql, .sql.gz, .dump lub .pgdump."
            )
        return path


def _detect_dump_format(path: Path) -> str | None:
    """Zwraca 'sql' / 'sql.gz' / 'pgdump' lub None gdy nie wiemy.

    Public helper — używany też w restore.py.
    """
    name = path.name.lower()
    if name.endswith(".sql.gz"):
        return "sql.gz"
    if name.endswith(".sql"):
        return "sql"
    if name.endswith(".dump") or name.endswith(".pgdump"):
        return "pgdump"
    return None
```

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_command.py -n auto 2>&1 | tee /tmp/runsite-task1-1.log
```

Expected: 3 zielone.

- [ ] **Step 5: Commit**

```bash
git add -A src/bpp/management/commands/run_site.py src/bpp/tests/test_run_site_command.py
git commit -m "feat(run_site): skeleton management command + walidacja args"
```

---

## Phase 2: Detect dump format + restore helper

### Task 2.1: `_run_site_helpers/restore.py`

**Files:**
- Create: `src/bpp/management/commands/_run_site_helpers/__init__.py`
- Create: `src/bpp/management/commands/_run_site_helpers/restore.py`
- Test: `src/bpp/tests/test_run_site_helpers.py`

- [ ] **Step 1: Failing tests (no Docker)**

`src/bpp/tests/test_run_site_helpers.py`:

```python
"""Testy helperów run_site (bez Dockera)."""

from pathlib import Path

import pytest

from bpp.management.commands._run_site_helpers.restore import (
    detect_dump_format,
    build_restore_command,
)


def test_detect_format_sql(tmp_path):
    p = tmp_path / "x.sql"
    p.write_text("")
    assert detect_dump_format(p) == "sql"


def test_detect_format_sql_gz(tmp_path):
    p = tmp_path / "x.sql.gz"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "sql.gz"


def test_detect_format_pgdump(tmp_path):
    p = tmp_path / "x.dump"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "pgdump"


def test_detect_format_pgdump_alt(tmp_path):
    p = tmp_path / "x.pgdump"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "pgdump"


def test_detect_format_uppercase_extension(tmp_path):
    p = tmp_path / "X.SQL.GZ"
    p.write_bytes(b"")
    assert detect_dump_format(p) == "sql.gz"


def test_detect_format_unknown(tmp_path):
    p = tmp_path / "x.tar"
    p.write_bytes(b"")
    assert detect_dump_format(p) is None


def test_build_restore_command_sql():
    cmd, decompress = build_restore_command(
        format="sql", container_id="abc123", db_user="bpp", db_name="bpp"
    )
    assert decompress is False
    assert cmd[:4] == ["docker", "exec", "-i", "abc123"]
    assert "psql" in cmd
    assert "-U" in cmd and "bpp" in cmd
    assert "-d" in cmd


def test_build_restore_command_sql_gz_decompresses():
    cmd, decompress = build_restore_command(
        format="sql.gz", container_id="abc123", db_user="bpp", db_name="bpp"
    )
    assert decompress is True  # caller pipes through gunzip
    assert "psql" in cmd


def test_build_restore_command_pgdump_uses_pg_restore():
    cmd, decompress = build_restore_command(
        format="pgdump", container_id="abc123", db_user="bpp", db_name="bpp"
    )
    assert decompress is False
    assert "pg_restore" in cmd
    assert "--clean" in cmd
    assert "--if-exists" in cmd
```

- [ ] **Step 2: Run — fail (ImportError)**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_helpers.py -n0 2>&1 | tee /tmp/runsite-task2-1-fail.log
```

- [ ] **Step 3: Implement**

`src/bpp/management/commands/_run_site_helpers/__init__.py`:

```python
"""Helpery dla komendy run_site."""
```

`src/bpp/management/commands/_run_site_helpers/restore.py`:

```python
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
    if name.endswith(".dump") or name.endswith(".pgdump"):
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
        decompress=True oznacza że caller musi wgnipsknąć stdin (sql.gz).
    """
    if format in ("sql", "sql.gz"):
        cmd = [
            "docker", "exec", "-i", container_id,
            "psql", "-v", "ON_ERROR_STOP=1",
            "-U", db_user, "-d", db_name,
        ]
        return cmd, format == "sql.gz"
    if format == "pgdump":
        cmd = [
            "docker", "exec", "-i", container_id,
            "pg_restore", "--clean", "--if-exists", "--no-owner",
            "-U", db_user, "-d", db_name,
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

    cmd, needs_decompress = build_restore_command(
        fmt, container_id, db_user, db_name
    )
    logger.info("Restore: %s (%s) → container %s", dump_path, fmt, container_id)

    if needs_decompress:
        # gunzip → docker exec -i psql
        with gzip.open(dump_path, "rb") as src:
            subprocess.run(cmd, stdin=src, check=True)
    else:
        with open(dump_path, "rb") as src:
            subprocess.run(cmd, stdin=src, check=True)
    logger.info("Restore: ukończony")
```

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_helpers.py -n auto 2>&1 | tee /tmp/runsite-task2-1.log
```

Expected: 9 zielonych.

- [ ] **Step 5: Refactor `run_site.py` — użyj helper-a**

W `src/bpp/management/commands/run_site.py` usuń lokalne `_detect_dump_format` i zamień na import:

```python
from ._run_site_helpers.restore import detect_dump_format
```

Sprawdź że istniejące testy command-line (Task 1.1) dalej przechodzą:

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_command.py -n auto
```

- [ ] **Step 6: Commit**

```bash
git add -A src/bpp/management/commands/_run_site_helpers/ src/bpp/management/commands/run_site.py src/bpp/tests/test_run_site_helpers.py
git commit -m "feat(run_site): detect_dump_format + build_restore_command helpers"
```

---

## Phase 3: Banner + browser opening

### Task 3.1: `_run_site_helpers/banner.py`

**Files:**
- Create: `src/bpp/management/commands/_run_site_helpers/banner.py`
- Test: append to `src/bpp/tests/test_run_site_helpers.py`

- [ ] **Step 1: Failing tests**

Append to `src/bpp/tests/test_run_site_helpers.py`:

```python
def test_banner_includes_all_endpoints():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="http://localhost:54321",
        admin_url="http://localhost:54321/admin/",
        admin_user="admin",
        admin_pass="admin",
        pg_host="127.0.0.1",
        pg_port=54322,
        redis_host="127.0.0.1",
        redis_port=54323,
        with_celery=False,
        dump_label="baseline",
    )
    assert "http://localhost:54321" in text
    assert "/admin/" in text
    assert "admin" in text
    assert "127.0.0.1:54322" in text
    assert "127.0.0.1:54323" in text
    assert "baseline" in text


def test_banner_celery_running_label():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="http://localhost:1",
        admin_url="http://localhost:1/admin/",
        admin_user="admin",
        admin_pass="admin",
        pg_host="x", pg_port=1, redis_host="x", redis_port=2,
        with_celery=True,
        dump_label="baseline",
    )
    assert "running" in text.lower()


def test_banner_celery_disabled_label():
    from bpp.management.commands._run_site_helpers.banner import format_banner

    text = format_banner(
        appserver_url="http://localhost:1",
        admin_url="http://localhost:1/admin/",
        admin_user="admin",
        admin_pass="admin",
        pg_host="x", pg_port=1, redis_host="x", redis_port=2,
        with_celery=False,
        dump_label="baseline",
    )
    assert "disabled" in text.lower() or "wyłączone" in text.lower()
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_helpers.py -n0 -k banner
```

- [ ] **Step 3: Implement**

`src/bpp/management/commands/_run_site_helpers/banner.py`:

```python
"""Banner z URL-ami i statusem stack-u."""


_TEMPLATE = """\
╔════════════════════════════════════════════════════════════════╗
║  BPP run-site — stack uruchomiony                              ║
╠════════════════════════════════════════════════════════════════╣
║  Appserver:  {appserver_url:<50}║
║  Admin:      {admin_url:<50}║
║              login: {admin_user:<10} hasło: {admin_pass:<19}║
║                                                                ║
║  PostgreSQL: {pg_endpoint:<50}║
║  Redis:      {redis_endpoint:<50}║
║                                                                ║
║  Celery:     {celery_label:<50}║
║  Dump:       {dump_label:<50}║
╠════════════════════════════════════════════════════════════════╣
║  Ctrl-C zakończy serwer i sprzątnie kontenery.                 ║
╚════════════════════════════════════════════════════════════════╝
"""


def format_banner(
    *,
    appserver_url: str,
    admin_url: str,
    admin_user: str,
    admin_pass: str,
    pg_host: str,
    pg_port: int,
    redis_host: str,
    redis_port: int,
    with_celery: bool,
    dump_label: str,
) -> str:
    return _TEMPLATE.format(
        appserver_url=appserver_url,
        admin_url=admin_url,
        admin_user=admin_user,
        admin_pass=admin_pass,
        pg_endpoint=f"{pg_host}:{pg_port} (bpp/password)",
        redis_endpoint=f"{redis_host}:{redis_port}",
        celery_label="running" if with_celery else "disabled",
        dump_label=dump_label,
    )
```

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_helpers.py -n auto -k banner
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(run_site): banner z URL-ami i statusem stack-u"
```

---

## Phase 4: Process management helpers

### Task 4.1: `_run_site_helpers/processes.py` + free port

**Files:**
- Create: `src/bpp/management/commands/_run_site_helpers/processes.py`
- Test: append to `src/bpp/tests/test_run_site_helpers.py`

- [ ] **Step 1: Failing tests**

```python
def test_find_free_port_returns_int_in_range():
    from bpp.management.commands._run_site_helpers.processes import find_free_port
    port = find_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535


def test_find_free_port_unique_calls():
    """Dwa wywołania zwracają różne porty (statystycznie prawie pewne)."""
    from bpp.management.commands._run_site_helpers.processes import find_free_port
    ports = {find_free_port() for _ in range(5)}
    # Bardzo rzadko może się zdarzyć kolizja, ale 5/5 to absurdalnie nieprawdopodobne.
    assert len(ports) >= 3
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_helpers.py -n0 -k port
```

- [ ] **Step 3: Implement**

`src/bpp/management/commands/_run_site_helpers/processes.py`:

```python
"""Spawn / wait / terminate dla runserver i celery worker subprocesses."""

from __future__ import annotations

import logging
import os
import signal
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


def _src_dir() -> Path:
    """Zwraca katalog `src/` (parent of bpp app)."""
    # __file__ = src/bpp/management/commands/_run_site_helpers/processes.py
    return Path(__file__).resolve().parents[4]


def _python_executable() -> str:
    """Path do Python interpreter — używa sys.executable, więc subprocess
    odziedzicza venv (uv run zachowany)."""
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
    """Spawn celery worker w background."""
    src = _src_dir()
    cmd = [
        _python_executable(),
        "-m", "celery",
        "-A", "django_bpp.tasks",
        "worker",
        "-l", "info",
    ]
    logger.info("Spawn celery: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd, env=env, cwd=str(src),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
```

- [ ] **Step 4: Run — pass (port tests)**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_helpers.py -n auto -k port
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(run_site): processes helpers (find_free_port, spawn_runserver, wait_terminate)"
```

---

## Phase 5: Pełna integracja w `Command.handle`

### Task 5.1: handle() — start + restore + superuser + banner + runserver

**Files:**
- Modify: `src/bpp/management/commands/run_site.py`

- [ ] **Step 1: Read settings env-var names**

Plan zakłada:
- `DJANGO_BPP_DB_HOST`, `DJANGO_BPP_DB_PORT`
- `DJANGO_BPP_REDIS_HOST`, `DJANGO_BPP_REDIS_PORT`
- `DJANGO_BPP_SKIP_DOTENV=1`

Sprawdź w `src/django_bpp/settings/base.py` linie 80-100 — potwierdź, że to dokładnie te nazwy. Jeśli istnieje `DJANGO_BPP_DB_USER`/`DJANGO_BPP_DB_PASSWORD` z innymi defaultami, też wstrzyknij dla kompletu.

- [ ] **Step 2: Implement `handle`**

`src/bpp/management/commands/run_site.py`:

```python
"""Management command: uruchom dev stack z testcontainerami.

Startuje PG+Redis na losowych portach (testcontainers), odtwarza dump,
tworzy superusera admin/admin, odpala runserver i blokuje. Ctrl-C
zatrzymuje runserver i sprząta kontenery.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
import webbrowser
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ._run_site_helpers.banner import format_banner
from ._run_site_helpers.processes import (
    find_free_port,
    run_subprocess_blocking,
    spawn_celery,
    spawn_runserver,
    wait_terminate,
)
from ._run_site_helpers.restore import detect_dump_format, restore_dump

logger = logging.getLogger(__name__)


_SUPERUSER_USERNAME = "admin"
_SUPERUSER_PASSWORD = "admin"  # noqa: S105 — dev tool, intencjonalnie hardcoded
_SUPERUSER_EMAIL = "admin@example.com"


class Command(BaseCommand):
    help = (
        "Odpala dev stack BPP: PG+Redis (testcontainers) + runserver. "
        "Opcjonalnie odtwarza dump i odpala celery."
    )

    def add_arguments(self, parser):
        # ... jak w Task 1.1 ...
        # (skopiować z poprzedniego stub-a; sprawdzić że --dry-run zostaje)
        parser.add_argument("--from-dump", type=str, default=None)
        parser.add_argument("--with-celery", action="store_true", default=False)
        parser.add_argument("--no-browser", action="store_true", default=False)
        parser.add_argument("--port", type=int, default=None)
        parser.add_argument("--reuse", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **opts):
        dump_path = self._validate_dump_arg(opts.get("from_dump"))
        if opts.get("dry_run"):
            self.stdout.write(self.style.SUCCESS("dry-run OK"))
            return

        from testcontainers_bpp.containers import (
            DockerNotRunningError,
            start_containers,
            stop_containers,
        )

        try:
            try:
                containers = start_containers(reuse=opts["reuse"])
            except DockerNotRunningError as exc:
                raise CommandError(
                    f"Docker daemon nie jest dostępny: {exc}"
                ) from exc

            celery_proc = None
            try:
                env = self._build_env(containers)
                self._restore_dump_if_needed(dump_path, containers)
                self._migrate(env)
                self._create_superuser(env)

                port = opts.get("port") or find_free_port()
                appserver_url = f"http://127.0.0.1:{port}"
                admin_url = f"{appserver_url}/admin/"

                self._print_banner(
                    appserver_url=appserver_url,
                    admin_url=admin_url,
                    containers=containers,
                    with_celery=opts["with_celery"],
                    dump_path=dump_path,
                )

                if opts["with_celery"]:
                    celery_proc = spawn_celery(env)

                if not opts["no_browser"]:
                    self._open_browser(admin_url)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nrunserver: {appserver_url}/  (Ctrl-C aby zakończyć)"
                    )
                )

                runserver_proc = spawn_runserver(port, env)
                runserver_proc.wait()
            finally:
                if celery_proc is not None:
                    wait_terminate(celery_proc)
        except KeyboardInterrupt:
            self.stdout.write("\n[run_site] Przerwane (Ctrl-C)")
        finally:
            try:
                stop_containers(containers)
            except Exception:
                logger.exception("[run_site] Failed to stop containers")

    # ── helpers ─────────────────────────────────────────────────────────

    def _validate_dump_arg(self, dump):
        if dump is None:
            return None
        path = Path(dump).expanduser().resolve()
        if not path.is_file():
            raise CommandError(f"Plik dump-a nie istnieje: {path}")
        if detect_dump_format(path) is None:
            raise CommandError(
                f"Nieobsługiwany format pliku {path.name}. "
                f"Użyj .sql, .sql.gz, .dump lub .pgdump."
            )
        return path

    def _build_env(self, containers) -> dict[str, str]:
        env = os.environ.copy()
        env["DJANGO_BPP_DB_HOST"] = containers.pg_host
        env["DJANGO_BPP_DB_PORT"] = str(containers.pg_port)
        env["DJANGO_BPP_REDIS_HOST"] = containers.redis_host
        env["DJANGO_BPP_REDIS_PORT"] = str(containers.redis_port)
        env["DJANGO_BPP_SKIP_DOTENV"] = "1"
        env["DJANGO_SUPERUSER_USERNAME"] = _SUPERUSER_USERNAME
        env["DJANGO_SUPERUSER_PASSWORD"] = _SUPERUSER_PASSWORD
        env["DJANGO_SUPERUSER_EMAIL"] = _SUPERUSER_EMAIL
        return env

    def _restore_dump_if_needed(self, dump_path, containers):
        if dump_path is None:
            return
        if containers.pg is None:
            raise CommandError(
                "Reuse=True nie ma kontenera do restore — "
                "uruchom raz bez --reuse aby zaimportować dump."
            )
        # Pobranie ID kontenera dla docker exec.
        container_id = containers.pg.get_wrapped_container().id
        self.stdout.write(f"[run_site] Restore: {dump_path} → PG container...")
        restore_dump(dump_path, container_id)
        self.stdout.write(self.style.SUCCESS("[run_site] Restore: ukończony"))

    def _migrate(self, env):
        self.stdout.write("[run_site] Migracja...")
        from ._run_site_helpers.processes import _python_executable, _src_dir

        cmd = [
            _python_executable(),
            str(_src_dir() / "manage.py"),
            "migrate", "--noinput",
        ]
        rc = run_subprocess_blocking(cmd, env=env, cwd=str(_src_dir()))
        if rc != 0:
            raise CommandError(f"manage.py migrate failed (rc={rc})")

    def _create_superuser(self, env):
        from ._run_site_helpers.processes import _python_executable, _src_dir

        self.stdout.write(
            f"[run_site] Superuser: {_SUPERUSER_USERNAME} / {_SUPERUSER_PASSWORD}"
        )
        cmd = [
            _python_executable(),
            str(_src_dir() / "manage.py"),
            "createsuperuser", "--noinput",
        ]
        rc = run_subprocess_blocking(cmd, env=env, cwd=str(_src_dir()))
        if rc != 0:
            self.stdout.write(self.style.WARNING(
                "[run_site] createsuperuser zwrócił błąd "
                "(prawdopodobnie user już istnieje — kontynuuję)"
            ))

    def _print_banner(self, *, appserver_url, admin_url, containers,
                       with_celery, dump_path):
        text = format_banner(
            appserver_url=appserver_url,
            admin_url=admin_url,
            admin_user=_SUPERUSER_USERNAME,
            admin_pass=_SUPERUSER_PASSWORD,
            pg_host=containers.pg_host,
            pg_port=containers.pg_port,
            redis_host=containers.redis_host,
            redis_port=containers.redis_port,
            with_celery=with_celery,
            dump_label=str(dump_path) if dump_path else "baseline",
        )
        self.stdout.write("")
        self.stdout.write(text)

    def _open_browser(self, url):
        try:
            # Mały opóźnienie żeby runserver zdążył wstać.
            # Browser open jest non-blocking — wykonujemy go w background thread.
            import threading

            def _delayed():
                time.sleep(2.0)
                webbrowser.open(url)

            threading.Thread(target=_delayed, daemon=True).start()
        except Exception:
            logger.exception("[run_site] Otwarcie przeglądarki nie powiodło się")
```

- [ ] **Step 3: Smoke check — args parsing dalej OK**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_command.py src/bpp/tests/test_run_site_helpers.py -n auto 2>&1 | tee /tmp/runsite-task5-1.log
```

Expected: wszystkie zielone (testy nie zaczepiają o pełen flow, tylko --dry-run i helpery).

- [ ] **Step 4: Manual smoke test (ASK USER ZANIM ROBISZ — wymaga Docker daemon + czeka)**

**TYLKO JEŻELI USER PROSI** o ręczny smoke (nie automatyzujemy w CI):

```bash
cd ~/Programowanie/bpp-worktrees/run-site-command
UV_NO_SYNC=1 uv run --all-extras src/manage.py run_site
# Powinien: spinner-up containers, restore baseline, createsuperuser admin/admin,
# print banner, open browser, runserver na losowym porcie.
# Ctrl-C powinno zatrzymać i sprzątnąć.
```

- [ ] **Step 5: Commit**

```bash
git add -A src/bpp/management/commands/run_site.py
git commit -m "feat(run_site): pełna integracja — start, restore, superuser, runserver"
```

---

## Phase 6: Newsfragment + finalny test

### Task 6.1: Newsfragment + push

- [ ] **Step 1: Sprawdź konwencję newsfragment**

```bash
cd ~/Programowanie/bpp-worktrees/run-site-command
ls src/bpp/newsfragments/ | head -5
```

Konwencja (wg memory): `+<descriptive-name>.<type>.rst`.

- [ ] **Step 2: Utwórz fragment**

`src/bpp/newsfragments/+run-site-command.feature.rst`:

```
Nowa komenda ``manage.py run_site`` — uruchamia dev stack BPP w testcontainerach
na losowych portach (PG + Redis), opcjonalnie odtwarza dump bazy
(``--from-dump path``, autodetect ``.sql`` / ``.sql.gz`` / ``.dump``), tworzy
superusera ``admin/admin``, odpala ``runserver`` i otwiera przeglądarkę.
Eliminuje konflikty portów przy wielu konfiguracjach BPP na jednym serwerze.
```

- [ ] **Step 3: Smoke test pełnego suite-u (subset)**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_run_site_command.py src/bpp/tests/test_run_site_helpers.py -n auto 2>&1 | tee /tmp/runsite-final.log | tail -10
```

- [ ] **Step 4: Commit + push**

```bash
git add -A
git commit -m "docs(newsfragment): manage.py run_site"
git push -u origin feature/run-site-command 2>&1 | tail -5
```

---

## Spec coverage matrix

| Wymaganie | Task |
|-----------|------|
| `--from-dump PATH` parsing + walidacja | 1.1 |
| `--with-celery` flag | 1.1 |
| `--no-browser` flag | 1.1 |
| `--port` flag | 1.1 |
| `--reuse` flag | 1.1 |
| Autodetect formatu (.sql/.sql.gz/.dump) | 2.1 |
| `restore_dump` przez `docker exec` | 2.1 |
| Banner z URL-ami i statusem | 3.1 |
| `find_free_port` | 4.1 |
| `spawn_runserver`, `spawn_celery`, `wait_terminate` | 4.1 |
| Start containers (testcontainers_bpp reuse) | 5.1 |
| Inject env vars (DB+Redis+SKIP_DOTENV+SUPERUSER_*) | 5.1 |
| `migrate --noinput` (subprocess) | 5.1 |
| `createsuperuser --noinput` (subprocess) | 5.1 |
| Open browser (default-on, threaded delay) | 5.1 |
| Spawn runserver, block until exit | 5.1 |
| Cleanup (stop_containers, terminate celery) | 5.1 |
| Newsfragment | 6.1 |

Wszystkie wymagania pokryte. **Brak placeholderów.** Ręczny smoke test (Step 4 of 5.1) wymaga interakcji użytkownika i nie jest automatyzowany.

---

## Co celowo poza zakresem

- `--detach` / daemon mode — komenda blokuje w foreground, koniec.
- Persystencja kontenerów po Ctrl-C — `--reuse` częściowo to daje, ale to opt-in.
- `rich` / TUI live banner — plain text wystarcza.
- Kontenerowy runserver — runserver leci lokalnie (autoreload).
- Custom hostname `bpp.local` w /etc/hosts — `localhost` wystarcza dla dev.
- Wsparcie dla `.tar` (pg_dump tar format) — rzadko używany, dorobimy gdy ktoś poprosi.
