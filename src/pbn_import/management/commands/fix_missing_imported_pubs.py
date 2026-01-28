"""Komenda naprawiająca brakujące importy publikacji PBN.

Po poprawce algorytmu dopasowania (matchuj_publikacje), publikacje które wcześniej
były błędnie rozpoznawane jako duplikaty, teraz mogą zostać poprawnie zaimportowane.

Ta komenda:
1. Znajduje publikacje PBN, które nie mają odpowiadającego rekordu w BPP
2. Dla każdej takiej publikacji uruchamia import z force=True
3. Dla każdej publikacji importuje również oświadczenia
"""

from argparse import RawTextHelpFormatter

from django.db import transaction
from tqdm import tqdm

from bpp.models import Dyscyplina_Naukowa, Rekord, Rodzaj_Zrodla
from pbn_api.management.commands.util import PBNBaseCommand
from pbn_api.models import Publication
from pbn_import.utils.command_helpers import (
    get_validated_default_jednostka,
    import_publication_with_statements,
)


class Command(PBNBaseCommand):
    help = """Importuje brakujące publikacje z PBN do BPP.

Znajduje publikacje PBN, które nie mają odpowiadającego rekordu w BPP
i próbuje je zaimportować. Dla każdej publikacji importowane są również
oświadczenia. Przydatne po poprawce algorytmu dopasowania (matchuj_publikacje),
gdy publikacje wcześniej błędnie rozpoznawane jako duplikaty mogą teraz
zostać poprawnie zaimportowane.

Credentials PBN są automatycznie pobierane z konfiguracji Uczelnia.

Przykłady użycia:

  # Testuj import bez zapisywania (transakcja wycofana)
  python manage.py fix_missing_imported_pubs --dry-run

  # Importuj brakujące publikacje (credentials z Uczelnia)
  python manage.py fix_missing_imported_pubs

  # Importuj tylko konkretną publikację
  python manage.py fix_missing_imported_pubs --pbn-uid=677d14f0fdbe833088ac3a40

  # Importuj tylko rozdziały (CHAPTER)
  python manage.py fix_missing_imported_pubs --type=CHAPTER
"""

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--jednostka",
            help="Nazwa domyślnej jednostki dla nowych autorów",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Wykonaj import, ale wycofaj transakcję na końcu (testowanie)",
        )
        parser.add_argument(
            "--pbn-uid",
            help="Importuj tylko publikację o podanym PBN UID",
        )
        parser.add_argument(
            "--type",
            choices=["ARTICLE", "BOOK", "EDITED_BOOK", "CHAPTER"],
            help="Importuj tylko publikacje danego typu",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Ogranicz liczbę importowanych publikacji",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Wyświetlaj szczegółowe informacje o każdej publikacji",
        )
        parser.add_argument(
            "--max-errors",
            type=int,
            default=None,
            help="Maksymalna liczba błędów, po której import zostanie przerwany",
        )

    def get_missing_publications(self, options):
        """Zwraca QuerySet publikacji PBN bez odpowiadających rekordów w BPP."""
        # Pobierz wszystkie pbn_uid_id które już są w BPP
        existing_pbn_uids = set(
            Rekord.objects.exclude(pbn_uid_id__isnull=True)
            .exclude(pbn_uid_id="")
            .values_list("pbn_uid_id", flat=True)
        )

        # Znajdź publikacje PBN, których nie ma w BPP
        missing = Publication.objects.exclude(pk__in=existing_pbn_uids)

        # Filtruj po konkretnym UID
        if options.get("pbn_uid"):
            missing = missing.filter(pk=options["pbn_uid"])

        # Filtruj po typie
        if options.get("type"):
            pub_type = options["type"]
            # Filtruj po typie w current_version
            missing = [
                p
                for p in missing
                if p.current_version
                and p.current_version.get("object", {}).get("type") == pub_type
            ]
            return missing

        return missing

    def _prepare_missing_list(self, options):
        """Przygotowuje listę brakujących publikacji z uwzględnieniem limitu."""
        missing = self.get_missing_publications(options)

        # Konwertuj do listy jeśli to QuerySet (dla możliwości filtrowania po typie)
        if hasattr(missing, "count"):
            missing_count = missing.count()
            missing_list = list(missing)
        else:
            missing_list = list(missing)
            missing_count = len(missing_list)

        if options.get("limit"):
            missing_list = missing_list[: options["limit"]]

        return missing_list, missing_count

    def _display_dry_run_summary(self, imported, skipped, errors, statements_total):
        """Wyświetla podsumowanie dla trybu dry-run."""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.WARNING("TRYB DRY-RUN - transakcja zostanie wycofana!")
        )
        self.stdout.write(f"Zaimportowano by: {imported} publikacji")
        if statements_total:
            self.stdout.write(f"Oświadczeń by: {statements_total}")
        if skipped:
            self.stdout.write(f"Pominięto by: {skipped} publikacji")
        if errors:
            self.stdout.write(self.style.ERROR(f"Błędów: {len(errors)} publikacji"))
        self.stdout.write(
            self.style.WARNING("\nŻadne zmiany nie zostały zapisane (--dry-run).")
        )

    def _process_single_publication(
        self, pub, client, default_jednostka, rodzaj_periodyk, dyscypliny_cache, verbose
    ):
        """Przetwarza pojedynczą publikację i zwraca wynik."""
        cv = pub.current_version
        pub_title = "?"
        pub_year = pub.year
        if cv:
            obj = cv.get("object", {})
            pub_title = obj.get("title", "?")

        result, error_info, statement_counts = import_publication_with_statements(
            pub.mongoId,
            client,
            default_jednostka,
            force=False,  # Publikacja nie istnieje w BPP, force niepotrzebne
            with_statements=True,  # Zawsze importuj oświadczenia
            rodzaj_periodyk=rodzaj_periodyk,
            dyscypliny_cache=dyscypliny_cache,
        )

        if error_info:
            if verbose:
                self.stderr.write(
                    self.style.ERROR(f"  Błąd dla {pub.pk}: {error_info['message']}")
                )
            return "error", {
                "pbn_uid": pub.pk,
                "title": pub_title,
                "year": pub_year,
                "message": error_info["message"],
                "traceback": error_info.get("traceback"),
            }

        if result:
            statements_count = statement_counts[0] if statement_counts else 0
            if verbose:
                stmt_info = (
                    f" (oświadczeń: {statements_count})" if statements_count else ""
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Zaimportowano: {pub.pk} -> {result}{stmt_info}"
                    )
                )
            return "imported", statements_count

        if verbose:
            self.stdout.write(self.style.WARNING(f"  Pominięto: {pub.pk}"))
        return "skipped", None

    def _import_publications(self, missing_list, client, default_jednostka, options):
        """Importuje listę publikacji i zwraca statystyki."""
        rodzaj_periodyk = Rodzaj_Zrodla.objects.filter(nazwa="periodyk").first()
        dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

        imported = 0
        skipped = 0
        errors = []
        statements_total = 0
        verbose = options.get("verbose")
        max_errors = options.get("max_errors")
        stopped_early = False

        self.stdout.write("\nImportowanie publikacji...")

        for pub in tqdm(missing_list, desc="Import"):
            if max_errors is not None and len(errors) >= max_errors:
                stopped_early = True
                self.stdout.write(
                    self.style.WARNING(
                        f"\nPrzerwano import po {max_errors} błędach (--max-errors)"
                    )
                )
                break

            status, data = self._process_single_publication(
                pub,
                client,
                default_jednostka,
                rodzaj_periodyk,
                dyscypliny_cache,
                verbose,
            )

            if status == "error":
                errors.append(data)
            elif status == "imported":
                imported += 1
                if isinstance(data, int):
                    statements_total += data
            else:
                skipped += 1

        return imported, skipped, errors, statements_total, stopped_early

    def _display_summary(
        self, imported, skipped, errors, statements_total, stopped_early
    ):
        """Wyświetla podsumowanie importu."""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Zaimportowano: {imported} publikacji"))
        if statements_total:
            self.stdout.write(self.style.SUCCESS(f"Oświadczeń: {statements_total}"))
        if skipped:
            self.stdout.write(self.style.WARNING(f"Pominięto: {skipped} publikacji"))
        if stopped_early:
            self.stdout.write(
                self.style.WARNING(
                    "Import przerwany z powodu osiągnięcia limitu błędów"
                )
            )
        if errors:
            self.stdout.write(self.style.ERROR(f"\nBłędy ({len(errors)} publikacji):"))
            self.stdout.write("-" * 50)
            for err in errors:
                title = err["title"]
                if len(title) > 60:
                    title = title[:57] + "..."
                self.stdout.write(self.style.ERROR(f"\nPBN UID: {err['pbn_uid']}"))
                self.stdout.write(f"Tytuł: {title}")
                self.stdout.write(f"Rok: {err['year']}")
                self.stdout.write(f"Błąd: {err['message']}")
                if err.get("traceback"):
                    self.stdout.write("\nTraceback:")
                    self.stdout.write(err["traceback"])

    def handle(self, *args, **options):
        dry_run = options.get("dry_run")

        with transaction.atomic():
            self._handle_inner(options, dry_run)

            if dry_run:
                # Wycofaj transakcję w trybie dry-run
                transaction.set_rollback(True)

    def _handle_inner(self, options, dry_run):
        """Wewnętrzna logika handle, wykonywana w transakcji."""
        self.stdout.write("Szukam brakujących publikacji PBN...")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("TRYB DRY-RUN - zmiany zostaną wycofane")
            )

        missing_list, missing_count = self._prepare_missing_list(options)

        self.stdout.write(f"Znaleziono {missing_count} brakujących publikacji PBN")

        if options.get("limit") and missing_count > options["limit"]:
            self.stdout.write(f"  (ograniczono do {options['limit']} z powodu --limit)")

        if missing_count == 0:
            self.stdout.write(
                self.style.SUCCESS("Wszystkie publikacje PBN są już zaimportowane!")
            )
            return

        # Pobierz domyślną jednostkę
        try:
            default_jednostka = get_validated_default_jednostka(
                jednostka_name=options.get("jednostka")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        self.stdout.write(f"Domyślna jednostka: {default_jednostka}")

        # Utwórz klienta PBN (credentials z PBNBaseCommand/Uczelnia)
        client = self.get_client(
            options["app_id"],
            options["app_token"],
            options["base_url"],
            options["user_token"],
            verbose=bool(options.get("verbose")),
        )

        # Importuj publikacje
        imported, skipped, errors, statements_total, stopped_early = (
            self._import_publications(missing_list, client, default_jednostka, options)
        )

        # Podsumowanie
        if dry_run:
            self._display_dry_run_summary(imported, skipped, errors, statements_total)
            if errors:
                self.stdout.write(
                    self.style.ERROR(f"\nBłędy ({len(errors)} publikacji):")
                )
                for err in errors:
                    title = err["title"]
                    if len(title) > 60:
                        title = title[:57] + "..."
                    self.stdout.write(self.style.ERROR(f"\nPBN UID: {err['pbn_uid']}"))
                    self.stdout.write(f"Tytuł: {title}")
                    self.stdout.write(f"Błąd: {err['message']}")
                    if err.get("traceback"):
                        self.stdout.write("\nTraceback:")
                        self.stdout.write(err["traceback"])
        else:
            self._display_summary(
                imported, skipped, errors, statements_total, stopped_early
            )
