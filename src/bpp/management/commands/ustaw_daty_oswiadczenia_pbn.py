"""
Management command do ustawiania daty oświadczenia PBN dla autorów publikacji.

Polecenie ustawia datę oświadczenia (data_oswiadczenia) w obiektach
Wydawnictwo_Ciagle_Autor oraz Wydawnictwo_Zwarte_Autor z elastycznym
filtrowaniem po roku i różnymi źródłami daty.
"""

from datetime import datetime

from django.core.management.base import CommandError
from django.db import transaction
from tqdm import tqdm

from bpp.management.base import BaseCommand
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor

# Domyślne daty oświadczenia dla lat ewaluacji
DEFAULT_DATES = {
    2022: datetime(2022, 12, 30).date(),
    2023: datetime(2023, 12, 29).date(),
    2024: datetime(2024, 12, 31).date(),
    2025: datetime(2025, 12, 31).date(),
}


class Command(BaseCommand):
    help = """
Ustawia datę oświadczenia PBN dla autorów publikacji.

Polecenie aktualizuje pole data_oswiadczenia w obiektach Wydawnictwo_Ciagle_Autor
oraz Wydawnictwo_Zwarte_Autor. Domyślnie wypełnia tylko rekordy z pustą datą
oświadczenia. Użyj --nadpisz aby nadpisać istniejące daty.

FILTROWANIE PO ROKU (wzajemnie wykluczające się):
  --rok RRRR              Pojedynczy rok
  --rok-min RRRR          Początek zakresu lat (wymaga --rok-max)
  --rok-max RRRR          Koniec zakresu lat (wymaga --rok-min)

ŹRÓDŁO DATY (wzajemnie wykluczające się):
  --data-oswiadczenia     Jawna data w formacie DD.MM.RRRR
  --uzyj-daty-utworzenia-rekordu
                          Użyj daty utworzenia rekordu (rekord.utworzono)
  --uzyj-daty-ostatniej-modyfikacji-rekordu
                          Użyj daty ostatniej modyfikacji (rekord.ostatnio_zmieniony)

Gdy nie podano źródła daty, używane są domyślne daty:
  2022 -> 30.12.2022
  2023 -> 29.12.2023
  2024 -> 31.12.2024
  2025 -> 31.12.2025

Dla lat spoza zakresu 2022-2025 wymagane jest jawne podanie daty.

PRZYKŁADY UŻYCIA:

  # Ustaw domyślne daty dla roku 2024
  python src/manage.py ustaw_daty_oswiadczenia_pbn --rok 2024

  # Ustaw jawną datę dla zakresu lat
  python src/manage.py ustaw_daty_oswiadczenia_pbn --rok-min 2022 --rok-max 2025 \\
      --data-oswiadczenia 31.12.2024

  # Użyj daty utworzenia rekordu
  python src/manage.py ustaw_daty_oswiadczenia_pbn --rok 2023 \\
      --uzyj-daty-utworzenia-rekordu

  # Użyj daty ostatniej modyfikacji
  python src/manage.py ustaw_daty_oswiadczenia_pbn --rok 2024 \\
      --uzyj-daty-ostatniej-modyfikacji-rekordu

  # Podgląd zmian (dry-run)
  python src/manage.py ustaw_daty_oswiadczenia_pbn --rok 2024 --dry-run

  # Nadpisz istniejące daty (domyślnie tylko puste są wypełniane)
  python src/manage.py ustaw_daty_oswiadczenia_pbn --rok 2024 --nadpisz
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

        # Grupa źródła daty
        date_source_group = parser.add_mutually_exclusive_group()
        date_source_group.add_argument(
            "--data-oswiadczenia",
            type=str,
            help="Jawna data oświadczenia w formacie DD.MM.RRRR",
        )
        date_source_group.add_argument(
            "--uzyj-daty-utworzenia-rekordu",
            action="store_true",
            help="Użyj daty utworzenia rekordu (rekord.utworzono)",
        )
        date_source_group.add_argument(
            "--uzyj-daty-ostatniej-modyfikacji-rekordu",
            action="store_true",
            help="Użyj daty ostatniej modyfikacji rekordu (rekord.ostatnio_zmieniony)",
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

    def _parse_explicit_date(self, date_str):
        """Parsuje jawną datę z formatu DD.MM.RRRR."""
        try:
            return datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError as err:
            raise CommandError(
                f"Nieprawidłowy format daty: '{date_str}'. "
                "Wymagany format: DD.MM.RRRR (np. 31.12.2024)"
            ) from err

    def _get_years_to_process(self, options):
        """Zwraca listę lat do przetworzenia na podstawie parametrów."""
        rok = options.get("rok")
        rok_min = options.get("rok_min")
        rok_max = options.get("rok_max")

        if rok is not None:
            return [rok]
        elif rok_min is not None and rok_max is not None:
            return list(range(rok_min, rok_max + 1))
        else:
            # Nie powinno wystąpić - wcześniejsza walidacja wymaga parametrów roku
            raise CommandError(
                "Wymagany jest parametr --rok lub para --rok-min/--rok-max."
            )

    def _get_date_source_type(self, options):
        """Określa typ źródła daty."""
        if options.get("data_oswiadczenia"):
            return "explicit"
        elif options.get("uzyj_daty_utworzenia_rekordu"):
            return "creation"
        elif options.get("uzyj_daty_ostatniej_modyfikacji_rekordu"):
            return "modification"
        else:
            return "default"

    def _validate_default_dates_available(self, years, date_source_type):
        """Sprawdza czy dla lat bez jawnej daty dostępne są daty domyślne."""
        if date_source_type != "default":
            return

        missing_years = [y for y in years if y not in DEFAULT_DATES]
        if missing_years:
            available_years = ", ".join(str(y) for y in sorted(DEFAULT_DATES.keys()))
            missing_years_str = ", ".join(str(y) for y in sorted(missing_years))
            raise CommandError(
                f"Brak domyślnej daty oświadczenia dla lat: {missing_years_str}. "
                f"Dostępne domyślne daty tylko dla lat: {available_years}. "
                f"Dla innych lat użyj --data-oswiadczenia, "
                f"--uzyj-daty-utworzenia-rekordu lub "
                f"--uzyj-daty-ostatniej-modyfikacji-rekordu."
            )

    def _get_date_for_object(self, obj, date_source_type, explicit_date):
        """Zwraca datę oświadczenia dla danego obiektu."""
        if date_source_type == "explicit":
            return explicit_date
        elif date_source_type == "creation":
            return obj.rekord.utworzono.date()
        elif date_source_type == "modification":
            return obj.rekord.ostatnio_zmieniony.date()
        else:  # default
            rok = obj.rekord.rok
            return DEFAULT_DATES.get(rok)

    def _build_year_filter(self, years):
        """Buduje filtr ORM dla lat."""
        if len(years) == 1:
            return {"rekord__rok": years[0]}
        else:
            return {"rekord__rok__gte": min(years), "rekord__rok__lte": max(years)}

    def _has_year_parameters(self, options):
        """Sprawdza czy podano jakiekolwiek parametry roku."""
        return (
            options.get("rok") is not None
            or options.get("rok_min") is not None
            or options.get("rok_max") is not None
        )

    def handle(self, *args, **options):
        # Bez parametrów roku - wyświetl pomoc (przed połączeniem z bazą)
        if not self._has_year_parameters(options):
            self.print_help("manage.py", "ustaw_daty_oswiadczenia_pbn")
            return

        # Walidacja parametrów (przed połączeniem z bazą)
        self._validate_year_parameters(options)

        # Określenie lat do przetworzenia
        years = self._get_years_to_process(options)

        # Określenie źródła daty
        date_source_type = self._get_date_source_type(options)

        # Walidacja dostępności domyślnych dat
        self._validate_default_dates_available(years, date_source_type)

        # Parsowanie jawnej daty jeśli podana
        explicit_date = None
        if options.get("data_oswiadczenia"):
            explicit_date = self._parse_explicit_date(options["data_oswiadczenia"])

        # Teraz wykonaj właściwą pracę w transakcji
        self._process_records(options, years, date_source_type, explicit_date)

    @transaction.atomic
    def _process_records(self, options, years, date_source_type, explicit_date):
        """Przetwarza rekordy w ramach transakcji."""
        dry_run = options["dry_run"]
        nadpisz = options["nadpisz"]

        # Wyświetl informacje o trybie działania
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "TRYB TESTOWY - żadne zmiany nie zostaną zapisane w bazie danych"
                )
            )

        # Informacja o konfiguracji
        years_str = str(years[0]) if len(years) == 1 else f"{min(years)}-{max(years)}"
        self.stdout.write(f"Lata do przetworzenia: {years_str}")

        source_descriptions = {
            "explicit": f"jawna data: {explicit_date}",
            "creation": "data utworzenia rekordu",
            "modification": "data ostatniej modyfikacji rekordu",
            "default": "domyślne daty per rok",
        }
        self.stdout.write(f"Źródło daty: {source_descriptions[date_source_type]}")

        if nadpisz:
            self.stdout.write(
                self.style.WARNING(
                    "Tryb nadpisywania - istniejące daty zostaną zmienione"
                )
            )
        else:
            self.stdout.write("Aktualizacja tylko rekordów z pustą datą oświadczenia")

        # Budowanie filtra
        year_filter = self._build_year_filter(years)

        total_updated = 0

        for klass in [
            Wydawnictwo_Ciagle_Autor.objects,
            Wydawnictwo_Zwarte_Autor.objects,
        ]:
            base_filter = year_filter.copy()
            if not nadpisz:
                base_filter["data_oswiadczenia__isnull"] = True

            objs = klass.filter(**base_filter).select_related("rekord")

            count = objs.count()
            if count == 0:
                self.stdout.write(
                    f"{klass.model.__name__}: brak rekordów do aktualizacji"
                )
                continue

            self.stdout.write(
                f"{klass.model.__name__}: {count} rekordów do aktualizacji"
            )

            for obj in tqdm(objs, desc=klass.model.__name__):
                new_date = self._get_date_for_object(
                    obj, date_source_type, explicit_date
                )
                if new_date is not None:
                    obj.data_oswiadczenia = new_date
                    obj.save()
                    total_updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Zaktualizowano {total_updated} rekordów")
        )

        if dry_run:
            # Anuluj transakcję w trybie testowym
            raise transaction.TransactionManagementError(
                "Dry run mode - rollback transaction"
            )
