import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Porównuje dane źródeł między BPP a PBN i zapisuje rozbieżności"

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-rok",
            type=int,
            default=2022,
            help="Minimalny rok do porównania (domyślnie: 2022)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Wyczyść istniejące rozbieżności przed porównaniem",
        )
        parser.add_argument(
            "--no-progress",
            action="store_true",
            help="Nie wyświetlaj paska postępu",
        )

    def handle(self, *args, **options):
        from pbn_komparator_zrodel.utils import KomparatorZrodelPBN

        komparator = KomparatorZrodelPBN(
            min_rok=options["min_rok"],
            clear_existing=options["clear"],
            show_progress=not options["no_progress"],
        )

        try:
            stats = komparator.run()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Zakończono porównywanie.\n"
                    f"  Przetworzono: {stats['processed']}\n"
                    f"  Rozbieżności punktów: {stats['points_discrepancies']}\n"
                    f"  Rozbieżności dyscyplin: {stats['discipline_discrepancies']}\n"
                    f"  Pominięto (brak PBN): {stats['skipped_no_pbn']}\n"
                    f"  Pominięto (brak danych): {stats['skipped_no_data']}\n"
                    f"  Błędy: {stats['errors']}"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Błąd podczas porównywania: {e}"))
            raise
