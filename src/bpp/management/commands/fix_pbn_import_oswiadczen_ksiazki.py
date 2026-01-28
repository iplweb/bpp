"""
Management command do naprawy typu odpowiedzialności autorów książek zaimportowanych z PBN.

Problem: Podczas importu książek z PBN, osoby będące redaktorami (EDITOR) mogły zostać
zaimportowane jako autorzy, jeśli brakowało danych afiliacji. W rezultacie integracja
oświadczeń nie mogła przypisać im dyscypliny.

Polecenie porównuje typ odpowiedzialności w oświadczeniach PBN (OswiadczenieInstytucji.type)
z typem w BPP (Wydawnictwo_Zwarte_Autor.typ_odpowiedzialnosci) i naprawia rozbieżności.
"""

from django.core.management.base import CommandError
from django.db import transaction
from tqdm import tqdm

from bpp.management.base import BaseCommand
from bpp.models import Typ_Odpowiedzialnosci, Wydawnictwo_Zwarte


class Command(BaseCommand):
    help = """
Naprawia typ odpowiedzialności autorów książek zaimportowanych z PBN.

PROBLEM:
  Podczas importu książek z PBN, osoby z listy "editors" mogły zostać
  zaimportowane jako "autor" zamiast "redaktor", gdy brakowało danych afiliacji.
  W efekcie integracja oświadczeń nie mogła przypisać im dyscypliny.

DZIAŁANIE:
  1. Znajduje książki z PBN (Wydawnictwo_Zwarte z pbn_uid_id)
  2. Dla każdej książki pobiera oświadczenia z OswiadczenieInstytucji
  3. Porównuje typ oświadczenia (AUTHOR/EDITOR) z typem w BPP
  4. Naprawia niezgodności (zmienia typ_odpowiedzialnosci)
  5. Opcjonalnie uruchamia integrację dyscypliny dla naprawionych rekordów

OPCJE:
  --dry-run               Podgląd zmian bez zapisywania
  --verbose               Szczegółowe logowanie
  --publikacja=PBN_UID    Napraw konkretną publikację (MongoDB ID)
  --integruj-dyscypliny   Po naprawie uruchom integrację dyscypliny

PRZYKŁADY UŻYCIA:

  # Podgląd wszystkich rozbieżności
  python src/manage.py fix_pbn_import_oswiadczen_ksiazki --dry-run --verbose

  # Naprawa konkretnej książki
  python src/manage.py fix_pbn_import_oswiadczen_ksiazki --publikacja=abc123

  # Naprawa wszystkich z integracją dyscyplin
  python src/manage.py fix_pbn_import_oswiadczen_ksiazki --integruj-dyscypliny
"""

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Wyświetl tylko informacje o rekordach do naprawienia, "
            "nie wykonuj zmian",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Szczegółowe logowanie",
        )
        parser.add_argument(
            "--publikacja",
            type=str,
            help="MongoDB ID konkretnej publikacji PBN do naprawienia",
        )
        parser.add_argument(
            "--integruj-dyscypliny",
            action="store_true",
            help="Po naprawie typu odpowiedzialności uruchom integrację dyscypliny",
        )

    def handle(self, *args, **options):
        self._process_records(options)

    def _print_config_info(self, options):
        """Wyświetla informacje o konfiguracji."""
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("TRYB TESTOWY - żadne zmiany nie zostaną zapisane")
            )

        if options["publikacja"]:
            self.stdout.write(f"Przetwarzanie publikacji: {options['publikacja']}")
        else:
            self.stdout.write("Przetwarzanie wszystkich książek z PBN")

        if options["integruj_dyscypliny"]:
            self.stdout.write("Integracja dyscyplin: TAK")

    def _print_summary(self, fixed_count, skipped_no_wa, skipped_matching, errors):
        """Wyświetla podsumowanie przetwarzania."""
        self.stdout.write("")
        self.stdout.write("Podsumowanie:")
        self.stdout.write(self.style.SUCCESS(f"  Naprawiono: {fixed_count}"))
        if skipped_no_wa > 0:
            self.stdout.write(
                f"  Pominięto (brak powiązania autor-publikacja): {skipped_no_wa}"
            )
        if skipped_matching > 0:
            self.stdout.write(f"  Pominięto (typ już zgodny): {skipped_matching}")
        if errors:
            self.stdout.write(self.style.ERROR(f"  Błędy: {len(errors)}"))
            for err in errors[:10]:
                self.stdout.write(f"    - {err}")
            if len(errors) > 10:
                self.stdout.write(f"    ... i {len(errors) - 10} więcej")

    def _get_books_queryset(self, publikacja_id):
        """Pobiera queryset książek do przetworzenia."""
        queryset = Wydawnictwo_Zwarte.objects.exclude(pbn_uid_id=None)
        if publikacja_id:
            queryset = queryset.filter(pbn_uid_id=publikacja_id)
            if not queryset.exists():
                raise CommandError(
                    f"Nie znaleziono publikacji z PBN UID: {publikacja_id}"
                )
        return queryset

    def _update_counters(self, result, counters, oswiadczenie, integruj_dyscypliny):
        """Aktualizuje liczniki na podstawie wyniku przetwarzania."""
        if result == "fixed":
            counters["fixed"] += 1
            if integruj_dyscypliny:
                counters["to_integrate"].append(oswiadczenie)
        elif result == "no_wa":
            counters["no_wa"] += 1
        elif result == "matching":
            counters["matching"] += 1

    @transaction.atomic
    def _process_records(self, options):
        """Przetwarza rekordy w ramach transakcji."""
        from pbn_api.models import OswiadczenieInstytucji

        dry_run = options["dry_run"]
        verbose = options["verbose"]
        integruj_dyscypliny = options["integruj_dyscypliny"]

        self._print_config_info(options)

        typ_autor = Typ_Odpowiedzialnosci.objects.get(nazwa="autor")
        typ_redaktor = Typ_Odpowiedzialnosci.objects.get(nazwa="redaktor")

        queryset = self._get_books_queryset(options.get("publikacja"))
        self.stdout.write(f"Znaleziono {queryset.count()} książek z PBN")

        counters = {"fixed": 0, "no_wa": 0, "matching": 0, "to_integrate": []}
        errors = []

        for book in tqdm(queryset, desc="Przetwarzanie książek"):
            oswiadczenia = OswiadczenieInstytucji.objects.filter(
                publicationId_id=book.pbn_uid_id
            ).select_related("personId")

            for oswiadczenie in oswiadczenia:
                try:
                    result = self._process_single_statement(
                        book, oswiadczenie, typ_autor, typ_redaktor, dry_run, verbose
                    )
                    self._update_counters(
                        result, counters, oswiadczenie, integruj_dyscypliny
                    )
                except Exception as e:
                    errors.append(
                        f"{book.tytul_oryginalny[:50]} / {oswiadczenie.personId}: {e}"
                    )

        if integruj_dyscypliny and counters["to_integrate"] and not dry_run:
            self._integrate_disciplines(counters["to_integrate"], verbose)

        self._print_summary(
            counters["fixed"], counters["no_wa"], counters["matching"], errors
        )

        if dry_run:
            raise transaction.TransactionManagementError(
                "Dry run mode - rollback transaction"
            )

    def _get_expected_typ(self, oswiadczenie, typ_autor, typ_redaktor):
        """Zwraca oczekiwany typ odpowiedzialności na podstawie oświadczenia PBN."""
        if oswiadczenie.type == "AUTHOR":
            return typ_autor
        elif oswiadczenie.type == "EDITOR":
            return typ_redaktor
        raise ValueError(f"Nieznany typ oświadczenia: {oswiadczenie.type}")

    def _find_autor_record(self, book, bpp_autor, expected_typ, verbose):
        """Znajduje rekord autor-publikacja.

        Returns:
            (wa, result) - wa to rekord lub None, result to "no_wa"/"matching"/None
        """
        try:
            return book.autorzy_set.get(autor=bpp_autor), None
        except book.autorzy_set.model.DoesNotExist:
            if verbose:
                self.stdout.write(
                    f"  Brak powiązania: {bpp_autor} w {book.tytul_oryginalny[:40]}"
                )
            return None, "no_wa"
        except book.autorzy_set.model.MultipleObjectsReturned:
            try:
                book.autorzy_set.get(
                    autor=bpp_autor, typ_odpowiedzialnosci=expected_typ
                )
                return None, "matching"
            except book.autorzy_set.model.DoesNotExist:
                return book.autorzy_set.filter(autor=bpp_autor).first(), None

    def _process_single_statement(
        self, book, oswiadczenie, typ_autor, typ_redaktor, dry_run, verbose
    ):
        """Przetwarza pojedyncze oświadczenie.

        Returns:
            "fixed" - naprawiono typ odpowiedzialności
            "no_wa" - brak powiązania autor-publikacja
            "matching" - typ już zgodny
        """
        expected_typ = self._get_expected_typ(oswiadczenie, typ_autor, typ_redaktor)

        bpp_autor = oswiadczenie.get_bpp_autor()
        if bpp_autor is None:
            if verbose:
                self.stdout.write(f"  Brak autora BPP: {oswiadczenie.personId}")
            return "no_wa"

        wa, result = self._find_autor_record(book, bpp_autor, expected_typ, verbose)
        if result:
            return result

        # wa should not be None here, but handle edge case
        if wa is None:
            return "no_wa"

        if wa.typ_odpowiedzialnosci == expected_typ:
            return "matching"

        old_typ = wa.typ_odpowiedzialnosci
        if verbose or dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"  {book.tytul_oryginalny[:50]}... / {bpp_autor}: "
                    f"{old_typ.nazwa} -> {expected_typ.nazwa}"
                )
            )

        if not dry_run:
            wa.typ_odpowiedzialnosci = expected_typ
            wa.save(update_fields=["typ_odpowiedzialnosci"])

        return "fixed"

    def _integrate_disciplines(self, records_to_integrate, verbose):
        """Uruchamia integrację dyscyplin dla naprawionych rekordów."""
        from bpp.models import Uczelnia
        from pbn_integrator.utils.statements import (
            integruj_oswiadczenia_z_instytucji_pojedyncza_praca,
        )

        self.stdout.write("")
        self.stdout.write("Integracja dyscyplin dla naprawionych rekordów...")

        default_jednostka = Uczelnia.objects.default.domyslna_jednostka
        noted_pub = set()
        noted_aut = set()

        for oswiadczenie in tqdm(records_to_integrate, desc="Integracja dyscyplin"):
            try:
                integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
                    oswiadczenie,
                    noted_pub,
                    noted_aut,
                    default_jednostka=default_jednostka,
                )
            except Exception as e:
                if verbose:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  Błąd integracji: {oswiadczenie.publicationId}: {e}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Zintegrowano dyscypliny dla {len(records_to_integrate)} rekordów"
            )
        )
