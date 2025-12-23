from django.core.management import BaseCommand

from bpp.models.wydawca import Poziom_Wydawcy


class Command(BaseCommand):
    help = "Klonuje poziomy wydawców z jednego roku na inny"

    def add_arguments(self, parser):
        parser.add_argument("rok_zrodlowy", type=int, help="Rok źródłowy (np. 2025)")
        parser.add_argument("rok_docelowy", type=int, help="Rok docelowy (np. 2026)")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Nadpisz istniejące poziomy nawet jeśli są inne",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pokaż co zostanie zrobione, bez zapisywania",
        )

    def handle(self, rok_zrodlowy, rok_docelowy, force, dry_run, verbosity, **options):
        # Pobierz wszystkie poziomy z roku źródłowego
        poziomy_zrodlowe = Poziom_Wydawcy.objects.filter(rok=rok_zrodlowy)

        utworzone = 0
        pominiete = 0
        ostrzezenia = 0
        nadpisane = 0

        for pw_zrodlowy in poziomy_zrodlowe:
            wydawca = pw_zrodlowy.wydawca

            # Sprawdź czy istnieje poziom w roku docelowym
            istniejacy = Poziom_Wydawcy.objects.filter(
                rok=rok_docelowy, wydawca=wydawca
            ).first()

            if istniejacy:
                if istniejacy.poziom == pw_zrodlowy.poziom:
                    # Taki sam poziom - pomiń
                    pominiete += 1
                else:
                    # Inny poziom
                    if force:
                        if not dry_run:
                            istniejacy.poziom = pw_zrodlowy.poziom
                            istniejacy.save()
                        nadpisane += 1
                        self.stdout.write(
                            f"NADPISANO: {wydawca.nazwa} - "
                            f"zmieniono z {istniejacy.poziom} na {pw_zrodlowy.poziom}"
                        )
                    else:
                        ostrzezenia += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"OSTRZEZENIE: {wydawca.nazwa} - "
                                f"istniejący poziom {istniejacy.poziom} != "
                                f"źródłowy {pw_zrodlowy.poziom} "
                                f"(użyj --force aby nadpisać)"
                            )
                        )
            else:
                # Nie istnieje - utwórz
                if not dry_run:
                    Poziom_Wydawcy.objects.create(
                        rok=rok_docelowy, wydawca=wydawca, poziom=pw_zrodlowy.poziom
                    )
                utworzone += 1

        # Podsumowanie
        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{prefix}Podsumowanie klonowania {rok_zrodlowy} -> {rok_docelowy}:"
            )
        )
        self.stdout.write(f"  Utworzono: {utworzone}")
        self.stdout.write(f"  Pominiętych (identyczny poziom): {pominiete}")
        self.stdout.write(f"  Nadpisanych (--force): {nadpisane}")
        if ostrzezenia:
            self.stdout.write(
                self.style.WARNING(f"  Ostrzeżeń (różny poziom): {ostrzezenia}")
            )
