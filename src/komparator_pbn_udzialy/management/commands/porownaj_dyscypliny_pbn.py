import logging

from django.core.management.base import BaseCommand

from komparator_pbn_udzialy.utils import porownaj_dyscypliny_pbn

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Porównuje dyscypliny między BPP (Wydawnictwo_*_Autor) a PBN (OswiadczenieInstytucji).
    Identyfikuje rozbieżności i zapisuje je do tabeli RozbieznoscDyscyplinPBN.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Wyczyść istniejące rozbieżności przed rozpoczęciem porównania",
        )

        parser.add_argument(
            "--no-progress",
            action="store_true",
            help="Nie pokazuj paska postępu",
        )

        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Włącz szczegółowe logowanie",
        )

    def handle(self, *args, **options):
        # Konfiguracja logowania
        if options["verbose"]:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        clear_existing = options.get("clear", False)
        show_progress = not options.get("no_progress", False)

        if clear_existing:
            self.stdout.write(
                self.style.WARNING(
                    "Usuwanie istniejących rozbieżności przed porównaniem..."
                )
            )

        self.stdout.write(
            self.style.SUCCESS("Rozpoczynam porównywanie dyscyplin BPP-PBN...")
        )

        try:
            # Uruchamiamy porównanie
            stats = porownaj_dyscypliny_pbn(
                clear_existing=clear_existing,
                show_progress=show_progress,
            )

            # Wyświetlamy podsumowanie
            total_missing = (
                stats["missing_publication"]
                + stats["missing_autor"]
                + stats["missing_link"]
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nPorównywanie zakończone pomyślnie!\n"
                    f"----------------------------------------\n"
                    f"Przetworzono oświadczeń: {stats['processed']}\n"
                    f"Znaleziono rozbieżności: {stats['discrepancies_found']}\n"
                    f"Brak publikacji w BPP: {stats['missing_publication']}\n"
                    f"Brak autora w BPP: {stats['missing_autor']}\n"
                    f"Brak powiązania autor-publikacja: {stats['missing_link']}\n"
                    f"Razem brakujących: {total_missing}\n"
                    f"Błędy: {stats['errors']}\n"
                )
            )

            if stats["errors"] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Wystąpiło {stats['errors']} błędów podczas przetwarzania. "
                        f"Sprawdź logi dla szczegółów."
                    )
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Błąd podczas porównywania: {str(e)}"))
            logger.exception("Błąd podczas wykonywania komendy porownaj_dyscypliny_pbn")
            raise
