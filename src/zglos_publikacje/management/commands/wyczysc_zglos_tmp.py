"""Czyszczenie porzuconych plików tymczasowych kreatora zgłoszeń.

Kasuje pliki starsze niż `--older-than-hours` (default 24) WYŁĄCZNIE
z katalogu tmp (`MEDIA_ROOT/protected/zglos_publikacje_tmp/`), tego samego
punktu prawdy co wizard (`storage.zglos_tmp_dir`).

Bezpieczeństwo wobec nakazu klienta „nigdy nie kasuj plików realnych
zgłoszeń" opiera się na KONSTRUKCJI: trwałe pliki ukończonych zgłoszeń
lądują w OSOBNYM katalogu (`protected/zglos_publikacje/`), którego ta
komenda nie dotyka. Dodatkowo strażnik ścieżki odmawia działania, gdy
rozwiązany katalog celu nie jest dokładnie skonfigurowanym katalogiem tmp.
"""

from __future__ import annotations

import pathlib
import time

from django.core.management.base import BaseCommand, CommandError

from zglos_publikacje.storage import ZGLOS_TMP_DIRNAME, zglos_tmp_dir


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

        # realpath — neutralizuje symlink i trailing slash zanim porównamy
        # basename ze strażnikiem.
        tmp = pathlib.Path(zglos_tmp_dir()).resolve()

        if not tmp.exists():
            # Świeża instalacja, zero uploadów — nie ma czego czyścić.
            # NIE wołamy iterdir() (rzuciłby FileNotFoundError).
            self.stdout.write(f"Katalog tmp nie istnieje ({tmp}) — nic do czyszczenia.")
            return

        # STRAŻNIK: równość basename (nie endswith). Zabezpieczenie przed
        # skasowaniem złego katalogu, gdyby punkt prawdy został podmieniony.
        if tmp.name != ZGLOS_TMP_DIRNAME:
            raise CommandError(
                "Strażnik ścieżki: katalog docelowy "
                f"'{tmp}' nie jest katalogiem tmp "
                f"'{ZGLOS_TMP_DIRNAME}' — odmawiam działania."
            )

        prog = time.time() - older_than_hours * 3600

        skasowane = 0
        skasowane_bajty = 0
        pominiete = 0

        for e in tmp.iterdir():
            # lstat — nie podążaj za linkiem; kasuj tylko zwykłe pliki, nigdy
            # symlinki (mogłyby wskazywać na plik trwały) ani katalogi.
            if not e.is_file() or e.is_symlink():
                pominiete += 1
                continue
            st = e.lstat()
            if st.st_mtime < prog:
                skasowane += 1
                skasowane_bajty += st.st_size
                if not dry_run:
                    e.unlink()
            else:
                pominiete += 1

        etykieta = "do skasowania" if dry_run else "skasowano"
        naglowek = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            f"{naglowek}{etykieta}: {skasowane} plików "
            f"({skasowane_bajty} bajtów); pominięto: {pominiete}."
        )
