"""Czyszczenie porzuconych plików tymczasowych kreatora zgłoszeń.

Cienki wrapper CLI na `zglos_publikacje.cleanup.wyczysc_tmp_pliki` (ten sam
rdzeń woła cykliczny celery task `zglos_publikacje.tasks`). Kasuje pliki
starsze niż `--older-than-hours` (default 24) WYŁĄCZNIE z katalogu tmp
(`MEDIA_ROOT/protected/zglos_publikacje_tmp/`). Trwałe pliki ukończonych
zgłoszeń są w osobnym katalogu i pozostają nietknięte.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from zglos_publikacje.cleanup import ZglosTmpGuardError, wyczysc_tmp_pliki


class Command(BaseCommand):
    help = (
        "Usuwa porzucone pliki tymczasowe kreatora zgłoszeń "
        "(protected/zglos_publikacje_tmp/) starsze niż zadany wiek. "
        "Nigdy nie dotyka katalogu trwałych plików zgłoszeń."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-hours",
            type=int,
            default=24,
            help="Kasuj pliki starsze niż tyle godzin (domyślnie 24).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pokaż co zostałoby skasowane, nie kasując niczego.",
        )

    def handle(self, *args, **options):
        older_than_hours = options["older_than_hours"]
        dry_run = options["dry_run"]

        try:
            wynik = wyczysc_tmp_pliki(
                older_than_hours=older_than_hours, dry_run=dry_run
            )
        except ValueError as e:
            raise CommandError(str(e)) from e
        except ZglosTmpGuardError as e:
            raise CommandError(f"Strażnik ścieżki: {e}") from e

        if wynik["katalog_nieobecny"]:
            self.stdout.write("Katalog tmp nie istnieje — nic do czyszczenia.")
            return

        etykieta = "do skasowania" if dry_run else "skasowano"
        naglowek = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            f"{naglowek}{etykieta}: {wynik['skasowane']} plików "
            f"({wynik['skasowane_bajty']} bajtów); pominięto: {wynik['pominiete']}."
        )
