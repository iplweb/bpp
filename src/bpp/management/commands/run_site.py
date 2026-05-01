"""Management command: uruchom dev stack z testcontainerami.

Startuje PG+Redis na losowych portach (testcontainers), odtwarza dump,
tworzy superusera admin/admin, odpala runserver i blokuje. Ctrl-C
zatrzymuje runserver i sprząta kontenery.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import webbrowser
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ._run_site_helpers.banner import format_banner
from ._run_site_helpers.processes import (
    _python_executable,
    _src_dir,
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

_BROWSER_OPEN_DELAY_SECONDS = 2.0


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
            help="Reuse named containers zamiast tworzyć nowe.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Tylko walidacja args + exit (do testów).",
        )

    def handle(self, *args, **opts):  # noqa: C901
        dump_path = self._validate_dump_arg(opts.get("from_dump"))
        if opts.get("dry_run"):
            self.stdout.write(self.style.SUCCESS("dry-run OK"))
            return

        from testcontainers_bpp.containers import (
            DockerNotRunningError,
            start_containers,
            stop_containers,
        )

        containers = None
        celery_proc = None
        try:
            try:
                # Suppress baseline gdy user dał własny dump — pg_restore
                # walczy z FK cascade gdy baseline już zaimportowany.
                containers = start_containers(
                    reuse=opts["reuse"],
                    load_baseline=(dump_path is None),
                )
            except DockerNotRunningError as exc:
                raise CommandError(f"Docker daemon nie jest dostępny: {exc}") from exc

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
            try:
                runserver_proc.wait()
            except KeyboardInterrupt:
                self.stdout.write("\n[run_site] Przerwane (Ctrl-C)")
                wait_terminate(runserver_proc)
        finally:
            if celery_proc is not None:
                wait_terminate(celery_proc)
            if containers is not None:
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
                f"Użyj .sql, .sql.gz, .dump, .pgdump lub .pg_dump."
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
        container_id = containers.pg.get_wrapped_container().id
        self.stdout.write(f"[run_site] Restore: {dump_path} → PG container...")
        restore_dump(dump_path, container_id)
        self.stdout.write(self.style.SUCCESS("[run_site] Restore: ukończony"))

    def _migrate(self, env):
        self.stdout.write("[run_site] Migracja...")
        cmd = [
            _python_executable(),
            str(_src_dir() / "manage.py"),
            "migrate",
            "--noinput",
        ]
        rc = run_subprocess_blocking(cmd, env=env, cwd=str(_src_dir()))
        if rc != 0:
            raise CommandError(f"manage.py migrate failed (rc={rc})")

    def _create_superuser(self, env):
        self.stdout.write(
            f"[run_site] Superuser: {_SUPERUSER_USERNAME} / {_SUPERUSER_PASSWORD}"
        )
        cmd = [
            _python_executable(),
            str(_src_dir() / "manage.py"),
            "createsuperuser",
            "--noinput",
        ]
        rc = run_subprocess_blocking(cmd, env=env, cwd=str(_src_dir()))
        if rc != 0:
            self.stdout.write(
                self.style.WARNING(
                    "[run_site] createsuperuser zwrócił błąd "
                    "(prawdopodobnie user już istnieje — kontynuuję)"
                )
            )

    def _print_banner(
        self, *, appserver_url, admin_url, containers, with_celery, dump_path
    ):
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
        def _delayed():
            try:
                time.sleep(_BROWSER_OPEN_DELAY_SECONDS)
                webbrowser.open(url)
            except Exception:
                logger.exception("[run_site] Otwarcie przeglądarki nie powiodło się")

        threading.Thread(target=_delayed, daemon=True).start()
