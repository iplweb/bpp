"""
Management command do uzupełniania dat oświadczeń z PBN do BPP.

Polecenie importuje datę oświadczenia (statedTimestamp) z OswiadczenieInstytucji
do odpowiadających rekordów Wydawnictwo_*_Autor.data_oswiadczenia.
"""

from django.core.management.base import CommandError
from django.db import transaction
from tqdm import tqdm

from bpp.management.base import BaseCommand


class Command(BaseCommand):
    help = """
Importuje daty oświadczeń z PBN (OswiadczenieInstytucji.statedTimestamp)
do odpowiednich rekordów autorów publikacji (Wydawnictwo_*_Autor.data_oswiadczenia).

WAŻNE: Polecenie używa pola statedTimestamp jako źródła daty.
       Rekordy bez statedTimestamp są pomijane.

FILTROWANIE PO ROKU (opcjonalne, wzajemnie wykluczające się):
  --rok RRRR              Pojedynczy rok publikacji
  --rok-min RRRR          Początek zakresu lat (wymaga --rok-max)
  --rok-max RRRR          Koniec zakresu lat (wymaga --rok-min)

OPCJE:
  --dry-run               Podgląd zmian bez zapisywania
  --nadpisz               Nadpisz istniejące daty (domyślnie tylko puste)

PRZYKŁADY UŻYCIA:

  # Podgląd zmian
  python src/manage.py fix_import_dat_oswiadczen_pbn --dry-run

  # Import dla roku 2024
  python src/manage.py fix_import_dat_oswiadczen_pbn --rok 2024

  # Import z nadpisaniem istniejących dat
  python src/manage.py fix_import_dat_oswiadczen_pbn --rok 2024 --nadpisz

  # Import dla zakresu lat
  python src/manage.py fix_import_dat_oswiadczen_pbn --rok-min 2022 --rok-max 2025
"""

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Wyświetl tylko informacje o rekordach do zaktualizowania, "
            "nie wykonuj zmian",
        )
        parser.add_argument(
            "--nadpisz",
            action="store_true",
            help="Nadpisz istniejące daty oświadczenia. Domyślnie aktualizowane "
            "są tylko rekordy z pustą datą.",
        )

        # Grupa filtrowania po roku
        year_group = parser.add_mutually_exclusive_group()
        year_group.add_argument(
            "--rok",
            type=int,
            help="Pojedynczy rok publikacji do przetworzenia",
        )

        parser.add_argument(
            "--rok-min",
            type=int,
            help="Minimalny rok publikacji (wymaga --rok-max)",
        )
        parser.add_argument(
            "--rok-max",
            type=int,
            help="Maksymalny rok publikacji (wymaga --rok-min)",
        )

    def _validate_year_parameters(self, options):
        """Waliduje parametry filtrowania po roku."""
        rok = options.get("rok")
        rok_min = options.get("rok_min")
        rok_max = options.get("rok_max")

        # Sprawdź czy --rok nie jest użyty razem z --rok-min/--rok-max
        if rok is not None and (rok_min is not None or rok_max is not None):
            raise CommandError(
                "Nie można używać --rok razem z --rok-min/--rok-max. "
                "Użyj --rok dla pojedynczego roku lub --rok-min i --rok-max "
                "dla zakresu lat."
            )

        # Sprawdź czy oba parametry zakresu są podane
        if (rok_min is not None) != (rok_max is not None):
            raise CommandError(
                "Parametry --rok-min i --rok-max muszą być używane razem."
            )

        # Sprawdź czy zakres jest poprawny
        if rok_min is not None and rok_max is not None:
            if rok_min > rok_max:
                raise CommandError(
                    f"--rok-min ({rok_min}) nie może być większy niż "
                    f"--rok-max ({rok_max})."
                )

    def _get_year_range(self, options):
        """Zwraca zakres lat do przetworzenia jako krotkę (min, max) lub None."""
        rok = options.get("rok")
        rok_min = options.get("rok_min")
        rok_max = options.get("rok_max")

        if rok is not None:
            return (rok, rok)
        elif rok_min is not None and rok_max is not None:
            return (rok_min, rok_max)
        else:
            return None

    def handle(self, *args, **options):
        # Walidacja parametrów (przed połączeniem z bazą)
        self._validate_year_parameters(options)

        # Określenie zakresu lat
        year_range = self._get_year_range(options)

        # Teraz wykonaj właściwą pracę w transakcji
        self._process_records(options, year_range)

    def _print_config_info(self, dry_run, nadpisz, year_range):
        """Wyświetla informacje o konfiguracji."""
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "TRYB TESTOWY - żadne zmiany nie zostaną zapisane w bazie danych"
                )
            )

        if year_range:
            if year_range[0] == year_range[1]:
                years_str = str(year_range[0])
            else:
                years_str = f"{year_range[0]}-{year_range[1]}"
            self.stdout.write(f"Lata do przetworzenia: {years_str}")
        else:
            self.stdout.write("Przetwarzanie wszystkich lat")

        self.stdout.write("Źródło daty: statedTimestamp z OswiadczenieInstytucji")

        if nadpisz:
            self.stdout.write(
                self.style.WARNING(
                    "Tryb nadpisywania - istniejące daty zostaną zmienione"
                )
            )
        else:
            self.stdout.write("Aktualizacja tylko rekordów z pustą datą oświadczenia")

    def _print_summary(
        self,
        updated_count,
        skipped_no_wa,
        skipped_year_filter,
        skipped_existing_date,
        missing_wa_records,
    ):
        """Wyświetla podsumowanie przetwarzania."""
        self.stdout.write("")
        self.stdout.write("Podsumowanie:")
        self.stdout.write(self.style.SUCCESS(f"  Zaktualizowano: {updated_count}"))
        if skipped_no_wa > 0:
            self.stdout.write(f"  Pominięto (brak WA): {skipped_no_wa}")
        if skipped_year_filter > 0:
            self.stdout.write(f"  Pominięto (filtr roku): {skipped_year_filter}")
        if skipped_existing_date > 0:
            self.stdout.write(f"  Pominięto (istniejąca data): {skipped_existing_date}")

        # Wypisz brakujące powiązania autor-publikacja
        if missing_wa_records:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"Brakujące powiązania autor-publikacja ({len(missing_wa_records)}):"
                )
            )
            for title, author_name, year, pbn_id in missing_wa_records:
                year_str = f", {year}" if year else ""
                self.stdout.write(
                    f"  - {author_name}: {title}{year_str} (PBN ID: {pbn_id})"
                )

    def _should_skip_by_year(self, wa, year_range):
        """Sprawdza czy rekord powinien być pominięty ze względu na rok."""
        if year_range is None:
            return False
        publication_year = wa.rekord.rok
        return publication_year < year_range[0] or publication_year > year_range[1]

    @transaction.atomic
    def _process_records(self, options, year_range):
        """Przetwarza rekordy w ramach transakcji."""
        from django.core.exceptions import ObjectDoesNotExist

        from pbn_api.models import OswiadczenieInstytucji

        dry_run = options["dry_run"]
        nadpisz = options["nadpisz"]

        self._print_config_info(dry_run, nadpisz, year_range)

        queryset = OswiadczenieInstytucji.objects.filter(
            statedTimestamp__isnull=False
        ).select_related("publicationId", "personId")

        total_count = queryset.count()
        self.stdout.write(f"Znaleziono {total_count} oświadczeń z datą statedTimestamp")

        updated_count = 0
        skipped_no_wa = 0
        skipped_year_filter = 0
        skipped_existing_date = 0
        missing_wa_records = []

        for oswiadczenie in tqdm(queryset, desc="Przetwarzanie"):
            try:
                wa = oswiadczenie.get_bpp_wa()
            except ObjectDoesNotExist:
                # Autor istnieje, publikacja istnieje, ale autor nie jest
                # powiązany z tą publikacją
                wa = None

            if wa is None:
                skipped_no_wa += 1
                # Zbierz informacje o brakującym powiązaniu
                pub = oswiadczenie.publicationId
                scientist = oswiadczenie.personId
                title = pub.title if pub else "(brak tytułu)"
                year = pub.year if pub else None
                pbn_id = pub.pk if pub else "(brak)"
                author_name = (
                    f"{scientist.lastName} {scientist.name}".strip()
                    if scientist
                    else "(brak autora)"
                )
                missing_wa_records.append((title, author_name, year, pbn_id))
                continue

            if self._should_skip_by_year(wa, year_range):
                skipped_year_filter += 1
                continue

            if not nadpisz and wa.data_oswiadczenia is not None:
                skipped_existing_date += 1
                continue

            wa.data_oswiadczenia = oswiadczenie.statedTimestamp
            wa.save(update_fields=["data_oswiadczenia"])
            updated_count += 1

        self._print_summary(
            updated_count,
            skipped_no_wa,
            skipped_year_filter,
            skipped_existing_date,
            missing_wa_records,
        )

        if dry_run:
            raise transaction.TransactionManagementError(
                "Dry run mode - rollback transaction"
            )
