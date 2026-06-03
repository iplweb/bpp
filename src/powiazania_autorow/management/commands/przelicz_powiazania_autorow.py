from django.core.management.base import BaseCommand

from powiazania_autorow.core import calculate_author_connections


class Command(BaseCommand):
    help = (
        "Przelicza od zera tabelę powiązań autorów (współautorstwa) na podstawie "
        "wydawnictw ciągłych, zwartych i patentów. Liczone w całości w SQL."
    )

    def handle(self, *args, **options):
        total = calculate_author_connections()
        self.stdout.write(self.style.SUCCESS(f"Przeliczono {total} powiązań autorów."))
