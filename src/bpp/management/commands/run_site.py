"""Management command: uruchom dev stack z testcontainerami.

Startuje PG+Redis na losowych portach (testcontainers), odtwarza dump,
tworzy superusera admin/admin, odpala runserver i blokuje. Ctrl-C
zatrzymuje runserver i sprząta kontenery.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import webbrowser
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from django_bpp.views_run_site_autologin import (
    AUTOLOGIN_ENV_VAR,
    AUTOLOGIN_URL_PATH,
)

from ._run_site_helpers.banner import format_banner
from ._run_site_helpers.log_multiplexer import (
    COLOR_CYAN,
    COLOR_GREEN,
    COLOR_YELLOW,
    LogMultiplexer,
)
from ._run_site_helpers.pbn_token import PbnTokenSource, fetch_pbn_token_via_ssh
from ._run_site_helpers.processes import (
    _python_executable,
    _src_dir,
    find_free_port,
    run_subprocess_blocking,
    spawn_celery,
    spawn_pg_logs,
    spawn_runserver,
    wait_for_http,
    wait_terminate,
)
from ._run_site_helpers.restore import detect_dump_format, restore_dump

logger = logging.getLogger(__name__)


_SUPERUSER_USERNAME = "admin"
_SUPERUSER_PASSWORD = "admin"  # noqa: S105 — dev tool, intencjonalnie hardcoded
_SUPERUSER_EMAIL = "admin@example.com"

_BROWSER_OPEN_TIMEOUT_SECONDS = 60.0
_AUTOLOGIN_TOKEN_BYTES = 32

_PBN_TOKEN_CACHE_FILENAME = ".saved_pbn_token"


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
            default=True,
            help="Odpal celery worker (default; --pool=solo). Backward-compat.",
        )
        parser.add_argument(
            "--no-celery",
            action="store_false",
            dest="with_celery",
            help="Nie uruchamiaj celery worker.",
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
            help=(
                "Persystencja kontenerów PG/Redis między uruchomieniami: "
                "pierwszy run inicjuje (baseline / --from-dump / migracje), "
                "kolejne podpinają się do istniejącego kontenera (running "
                "lub stopped) i pomijają inicjalizację. Kontenery NIE są "
                "zatrzymywane na exit. Aby zacząć od zera: "
                "docker rm -f bpp-tc-pg bpp-tc-redis."
            ),
        )
        parser.add_argument(
            "--get-pbn-token-from",
            type=str,
            default=None,
            metavar="USERNAME@SSH-HOST",
            help=(
                "Po migracji pobierz token PBN z hosta SSH przez "
                "dump_pbn_token | load_pbn_token. USERNAME = nazwa "
                "użytkownika Django (taka sama lokalnie i zdalnie); "
                "SSH-HOST = alias z ~/.ssh/config (z wpisanym ssh-userem). "
                "Pierwszy fetch jest cache'owany w .saved_pbn_token w "
                "korzeniu repo — usuń ten plik aby wymusić ponowne SSH."
            ),
        )
        parser.add_argument(
            "--remote-deploy-path",
            type=str,
            default="~/bpp-deploy",
            metavar="PATH",
            help=(
                "Ścieżka do checkoutu bpp-deploy (z plikami docker-compose) "
                "na zdalnym hoście; używana razem z --get-pbn-token-from. "
                "Default: ~/bpp-deploy."
            ),
        )
        parser.add_argument(
            "--remote-compose-service",
            type=str,
            default="appserver",
            metavar="SERVICE",
            help=(
                "Nazwa serwisu w docker compose, w którym odpalić "
                "dump_pbn_token. Default: appserver."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Tylko walidacja args + exit (do testów).",
        )

    def handle(self, *args, **opts):  # noqa: C901
        dump_path = self._validate_dump_arg(opts.get("from_dump"))
        pbn_token_source = self._validate_pbn_token_source(
            opts.get("get_pbn_token_from")
        )
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

            autologin_token = secrets.token_urlsafe(_AUTOLOGIN_TOKEN_BYTES)
            env = self._build_env(containers, autologin_token=autologin_token)
            self._restore_dump_if_needed(dump_path, containers)
            self._migrate(env)
            self._create_superuser(env)
            if pbn_token_source is not None:
                fetch_pbn_token_via_ssh(
                    pbn_token_source,
                    remote_deploy_path=opts["remote_deploy_path"],
                    remote_compose_service=opts["remote_compose_service"],
                    local_env=env,
                    log=self.stdout.write,
                    cache_path=_src_dir().parent / _PBN_TOKEN_CACHE_FILENAME,
                )

            port = opts.get("port") or find_free_port()
            # ZAWSZE http:// — runserver nie ma SSL-a, https:// = błąd
            # połączenia. Używamy `localhost` zamiast `127.0.0.1`, żeby
            # uniknąć HSTS cache w Safari upgrade'ującego http://127.0.0.1
            # do https://.
            appserver_url = f"http://localhost:{port}"
            assert appserver_url.startswith("http://"), (
                "appserver_url musi być http:// — runserver nie obsługuje SSL"
            )
            admin_url = f"{appserver_url}/admin/"

            self._print_banner(
                appserver_url=appserver_url,
                admin_url=admin_url,
                containers=containers,
                with_celery=opts["with_celery"],
                dump_path=dump_path,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nrunserver: {appserver_url}/  (Ctrl-C aby zakończyć)\n"
                )
            )

            mux = LogMultiplexer()

            runserver_proc = spawn_runserver(port, env)
            mux.add_stream("web", COLOR_CYAN, runserver_proc.stdout)

            if not opts["no_browser"]:
                self._open_browser_when_ready(
                    host="127.0.0.1",
                    port=port,
                    url=(
                        f"{appserver_url}/{AUTOLOGIN_URL_PATH}?token={autologin_token}"
                    ),
                )

            if opts["with_celery"]:
                celery_proc = spawn_celery(env)
                mux.add_stream("celery", COLOR_GREEN, celery_proc.stdout)

            pg_logs_proc = self._maybe_spawn_pg_logs(containers, mux)

            try:
                runserver_proc.wait()
            except KeyboardInterrupt:
                self.stdout.write("\n[run_site] Przerwane (Ctrl-C)")
                wait_terminate(runserver_proc)
                if opts["reuse"]:
                    from testcontainers_bpp.containers import (
                        _PG_NAME,
                        _REDIS_NAME,
                    )

                    self.stdout.write(
                        f"[run_site] Kontenery wciąż działają. "
                        f"Usuń ręcznie: docker rm -f {_PG_NAME} {_REDIS_NAME}"
                    )
            finally:
                if pg_logs_proc is not None:
                    wait_terminate(pg_logs_proc)
        finally:
            if celery_proc is not None:
                wait_terminate(celery_proc)
            if containers is not None:
                try:
                    stop_containers(containers)
                except Exception:
                    logger.exception("[run_site] Failed to stop containers")

    # ── helpers ─────────────────────────────────────────────────────────

    def _validate_pbn_token_source(self, raw):
        if raw is None:
            return None
        try:
            return PbnTokenSource.parse(raw)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

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

    def _build_env(self, containers, *, autologin_token: str) -> dict[str, str]:
        env = os.environ.copy()
        env["DJANGO_BPP_DB_HOST"] = containers.pg_host
        env["DJANGO_BPP_DB_PORT"] = str(containers.pg_port)
        env["DJANGO_BPP_REDIS_HOST"] = containers.redis_host
        env["DJANGO_BPP_REDIS_PORT"] = str(containers.redis_port)
        env["DJANGO_BPP_SKIP_DOTENV"] = "1"
        env["DJANGO_SUPERUSER_USERNAME"] = _SUPERUSER_USERNAME
        env["DJANGO_SUPERUSER_PASSWORD"] = _SUPERUSER_PASSWORD
        env["DJANGO_SUPERUSER_EMAIL"] = _SUPERUSER_EMAIL
        env[AUTOLOGIN_ENV_VAR] = autologin_token
        return env

    def _restore_dump_if_needed(self, dump_path, containers):
        if dump_path is None:
            return
        if containers.pg is None:
            # --reuse + istniejący kontener: ma już dane, nie nadpisujemy
            # (restore mógłby zostawić bazę w połowicznym stanie albo
            # walczyć z FK cascade). Ale użycie --reuse + --from-dump
            # w tym samym wywołaniu to też normalny workflow ("pierwszy
            # raz przywieź dump, potem reuse na bieżącym stanie") —
            # więc tylko ostrzegamy zamiast wywalać CommandError.
            self.stderr.write(
                self.style.ERROR(
                    "[run_site] OSTRZEŻENIE: --from-dump zignorowane — "
                    "kontener bpp-tc-pg już istnieje z danymi i nie "
                    "nadpisuję istniejącej bazy."
                )
            )
            self.stderr.write(
                self.style.ERROR(
                    "[run_site] Aby załadować nowy dump: "
                    "docker rm -f bpp-tc-pg bpp-tc-redis, "
                    "potem run_site --reuse --from-dump <dump>."
                )
            )
            return
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
        """Utwórz lub nadpisz superusera + skasuj wymóg zmiany hasła.

        Idempotentne: gdy user "admin" już istnieje (np. po restore dump-a
        z prod-u), hasło i flagi (is_active/is_staff/is_superuser) są
        nadpisywane. Wpisy w ``password_policies.PasswordChangeRequired``
        są kasowane, żeby admin nie dostawał propozycji zmiany hasła
        zaraz po zalogowaniu.
        """
        self.stdout.write(
            f"[run_site] Superuser: {_SUPERUSER_USERNAME} / {_SUPERUSER_PASSWORD}"
        )
        cmd = [
            _python_executable(),
            str(_src_dir() / "manage.py"),
            "runsite_setup_admin",
        ]
        rc = run_subprocess_blocking(cmd, env=env, cwd=str(_src_dir()))
        if rc != 0:
            raise CommandError(f"runsite_setup_admin failed (rc={rc})")

    def _print_banner(
        self,
        *,
        appserver_url,
        admin_url,
        containers,
        with_celery,
        dump_path,
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

    def _maybe_spawn_pg_logs(self, containers, mux):
        """Podpina ``docker logs -f`` dla PG do multipleksera.

        Gdy reuse'ujemy istniejący kontener, ``containers.pg`` jest None —
        odczytujemy ID po nazwie ``bpp-tc-pg`` (best-effort; jeśli się nie
        uda, po prostu nie strumieniujemy logów, web/celery wystarczą).
        """
        container_id = None
        if containers.pg is not None:
            try:
                container_id = containers.pg.get_wrapped_container().id
            except Exception:
                logger.exception("[run_site] nie mogę odczytać ID PG containera")
        else:
            try:
                import docker

                container_id = docker.from_env().containers.get("bpp-tc-pg").id
            except Exception:
                logger.warning("[run_site] reuse PG: nie znaleziono bpp-tc-pg do logs")

        if container_id is None:
            return None
        try:
            proc = spawn_pg_logs(container_id)
        except FileNotFoundError:
            logger.warning("[run_site] 'docker' nie znaleziony w PATH — bez logów PG")
            return None
        mux.add_stream("pg", COLOR_YELLOW, proc.stdout)
        return proc

    def _open_browser_when_ready(self, *, host: str, port: int, url: str):
        """Otwórz przeglądarkę dopiero gdy Django realnie odpowiada HTTP-em.

        TCP-only check (``wait_for_listen``) zwracał True w momencie
        ``bind()+listen()`` runservera — zanim Django dokończył ładowanie
        URLConf/middleware. Safari trafiało w warming app i cachował błąd.
        Probe HTTP-em pod ``/admin/login/`` rozgrzewa URL resolver — gdy
        odpowiedź wraca z statusem < 500, Django jest naprawdę gotowy.
        """
        probe_url = f"http://{host}:{port}/admin/login/"

        def _wait_and_open():
            try:
                if not wait_for_http(probe_url, timeout=_BROWSER_OPEN_TIMEOUT_SECONDS):
                    logger.warning(
                        "[run_site] runserver nie odpowiedział HTTP-em w %.0fs — "
                        "pomijam otwarcie przeglądarki",
                        _BROWSER_OPEN_TIMEOUT_SECONDS,
                    )
                    return
                webbrowser.open(url)
            except Exception:
                logger.exception("[run_site] Otwarcie przeglądarki nie powiodło się")

        threading.Thread(target=_wait_and_open, daemon=True).start()
