"""Szyfruje zapisane jawnie sekrety integracji (pola EncryptedTextField).

Idempotentna: wartości już zaszyfrowane są pomijane. Przydatna, gdy klucz
DJANGO_BPP_FIELD_ENCRYPTION_KEY dodano po migracji. Z ``--rotuj``
dodatkowo przepisuje istniejące szyfrogramy na pierwszy (główny) klucz —
po rotacji stare klucze można usunąć z konfiguracji.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from bpp.fields import multifernet
from bpp.sekrety import kolumny_szyfrowane, przeszyfruj, zaszyfruj_jawne


class Command(BaseCommand):
    help = (
        "Szyfruje jawne wartości sekretów integracji w bazie; z --rotuj "
        "przepisuje szyfrogramy na główny klucz."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--rotuj",
            action="store_true",
            help="Przepisz istniejące szyfrogramy na pierwszy klucz.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Tylko policz, nic nie zapisuj.",
        )

    def handle(self, *args, rotuj=False, dry_run=False, **options):
        if multifernet() is None:
            raise CommandError(
                "Brak klucza szyfrowania — ustaw DJANGO_BPP_FIELD_ENCRYPTION_KEY."
            )

        prefiks = "[dry-run] " if dry_run else ""
        nieodszyfrowalne_razem = 0
        with transaction.atomic():
            for tabela, kolumna in kolumny_szyfrowane():
                ile = zaszyfruj_jawne(connection, tabela, kolumna, dry_run=dry_run)
                self.stdout.write(f"{prefiks}{tabela}.{kolumna}: zaszyfrowano {ile}")
                if rotuj:
                    ile, nieodszyfrowalne = przeszyfruj(
                        connection, tabela, kolumna, dry_run=dry_run
                    )
                    nieodszyfrowalne_razem += nieodszyfrowalne
                    self.stdout.write(
                        f"{prefiks}{tabela}.{kolumna}: przeszyfrowano {ile}, "
                        f"nie do odczytania {nieodszyfrowalne}"
                    )

        if nieodszyfrowalne_razem:
            self.stderr.write(
                f"Uwaga: {nieodszyfrowalne_razem} wartości nie da się "
                "odszyfrować żadnym ze skonfigurowanych kluczy — pozostawiono "
                "je bez zmian. Dodaj brakujący klucz albo wpisz te sekrety "
                "ponownie."
            )
