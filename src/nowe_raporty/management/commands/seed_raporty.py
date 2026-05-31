from django.core.management.base import BaseCommand

from nowe_raporty.seeding import seed_default_reports


class Command(BaseCommand):
    help = (
        "Zakłada domyślne definicje raportów (autor/jednostka/wydział/uczelnia) "
        "jeśli ich nie ma. Idempotentne - nie nadpisuje istniejących danych."
    )

    def handle(self, *args, **options):
        utworzone, pominiete = seed_default_reports()

        for slug in utworzone:
            self.stdout.write(self.style.SUCCESS(f"Utworzono raport: {slug}"))
        for slug in pominiete:
            self.stdout.write(f"Pominięto (już istnieje): {slug}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Gotowe. Utworzono: {len(utworzone)}, pominięto: {len(pominiete)}."
            )
        )
