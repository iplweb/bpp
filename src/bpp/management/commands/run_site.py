"""Management command: uruchom dev stack z testcontainerami.

Startuje PG+Redis na losowych portach (testcontainers), odtwarza dump,
tworzy superusera admin/admin, odpala runserver i blokuje. Ctrl-C
zatrzymuje runserver i sprząta kontenery.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def _detect_dump_format(path: Path) -> str | None:
    """Zwraca 'sql' / 'sql.gz' / 'pgdump' lub None.

    Detekcja po extension, case-insensitive. Helper przeniesiony do
    _run_site_helpers.restore w Task 2.1 — tu duplikat dla skeleton-u.
    """
    name = path.name.lower()
    if name.endswith(".sql.gz"):
        return "sql.gz"
    if name.endswith(".sql"):
        return "sql"
    if name.endswith(".dump") or name.endswith(".pgdump"):
        return "pgdump"
    return None


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

    def handle(self, *args, **opts):
        self._validate_dump_arg(opts.get("from_dump"))
        if opts.get("dry_run"):
            self.stdout.write(self.style.SUCCESS("dry-run OK"))
            return

        raise CommandError("Pełna implementacja w toku — na razie tylko --dry-run.")

    def _validate_dump_arg(self, dump):
        if dump is None:
            return None
        path = Path(dump).expanduser().resolve()
        if not path.is_file():
            raise CommandError(f"Plik dump-a nie istnieje: {path}")
        if _detect_dump_format(path) is None:
            raise CommandError(
                f"Nieobsługiwany format pliku {path.name}. "
                f"Użyj .sql, .sql.gz, .dump lub .pgdump."
            )
        return path
