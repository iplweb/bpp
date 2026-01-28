"""Import publikacji z PBN do BPP po PBN UID."""

from pbn_api.exceptions import HttpException
from pbn_api.management.commands.util import PBNBaseCommand
from pbn_import.utils.command_helpers import (
    get_validated_default_jednostka,
    import_publication_with_statements,
)
from pbn_integrator.importer import get_or_download_publication


class Command(PBNBaseCommand):
    help = (
        "Importuje publikację z PBN do BPP na podstawie PBN UID.\n"
        "Przykład: pbn_importuj_uid 6760027dfdbe834e36a456be"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "pbn_uids",
            nargs="+",
            help="Jeden lub więcej identyfikatorów PBN UID publikacji",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Wymuś reimport nawet jeśli publikacja już istnieje w BPP",
        )

        parser.add_argument(
            "--with-oswiadczenia",
            action="store_true",
            default=False,
            help="Importuj również oświadczenia instytucji dla publikacji",
        )

        parser.add_argument(
            "--jednostka",
            type=str,
            default=None,
            help="Nazwa jednostki domyślnej dla autorów",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Pobierz i wyświetl informacje o publikacji bez importu do BPP",
        )

    def _dry_run_single_publication(self, pbn_uid, client):
        """Fetch and display publication info without importing. Returns True on success."""
        pbn_publication = get_or_download_publication(pbn_uid, client)

        if pbn_publication is None:
            self.stderr.write(self.style.WARNING("  Nie znaleziono publikacji w PBN"))
            return False

        self.stdout.write(self.style.SUCCESS(f"  Tytuł: {pbn_publication.title}"))
        self.stdout.write(f"  Rok: {pbn_publication.year}")
        self.stdout.write(f"  Typ: {pbn_publication.type()}")

        if pbn_publication.doi:
            self.stdout.write(f"  DOI: {pbn_publication.doi}")
        if pbn_publication.isbn:
            self.stdout.write(f"  ISBN: {pbn_publication.isbn}")

        # Wyświetl autorów
        autorzy = pbn_publication.autorzy
        if autorzy:
            autor_count = pbn_publication.policz_autorow()
            self.stdout.write(f"  Autorów: {autor_count}")
            for role, persons in autorzy.items():
                role_pl = {
                    "authors": "Autorzy",
                    "editors": "Redaktorzy",
                    "translators": "Tłumacze",
                    "translationEditors": "Red. przekładu",
                }.get(role, role)
                persons_list = (
                    list(persons.values()) if isinstance(persons, dict) else persons
                )
                names = []
                for p in persons_list[:5]:
                    # PBN uses familyName/givenNames or lastName/name
                    last = p.get("familyName") or p.get("lastName", "")
                    first = p.get("givenNames") or p.get("name", "")
                    names.append(f"{last} {first}".strip())
                if len(persons_list) > 5:
                    names.append(f"... (+{len(persons_list) - 5})")
                self.stdout.write(f"    {role_pl}: {', '.join(names)}")

        # Sprawdź czy istnieje w BPP
        rekord_bpp = pbn_publication.rekord_w_bpp
        if rekord_bpp:
            self.stdout.write(
                self.style.WARNING(
                    f"  Istnieje w BPP: {rekord_bpp} (ID: {rekord_bpp.pk})"
                )
            )
        else:
            self.stdout.write(self.style.NOTICE("  Nie istnieje jeszcze w BPP"))

        return True

    def _import_single_publication(
        self, pbn_uid, client, default_jednostka, options, inconsistency_callback
    ):
        """Import a single publication by PBN UID. Returns True on success."""
        result, error_info, statement_counts = import_publication_with_statements(
            pbn_uid,
            client,
            default_jednostka,
            force=options["force"],
            with_statements=options["with_oswiadczenia"],
            inconsistency_callback=inconsistency_callback,
        )

        if error_info:
            self.stderr.write(self.style.WARNING(f"  {error_info['message']}"))

        if result is None:
            if not error_info:
                self.stderr.write(self.style.WARNING("  Import nie zwrócił wyniku"))
            return False

        self.stdout.write(
            self.style.SUCCESS(f"  OK: {result.tytul_oryginalny} ({result.rok})")
        )
        self.stdout.write(f"  Typ: {result._meta.verbose_name}")

        if options["with_oswiadczenia"] and statement_counts:
            pobrano, zintegrowano = statement_counts
            self.stdout.write(
                f"  Oświadczeń: pobrano {pobrano}, zintegrowano {zintegrowano}"
            )

        return True

    def _print_summary(
        self, success_count, error_count, inconsistencies, dry_run=False
    ):
        """Print import summary."""
        self.stdout.write("\n" + "=" * 50)
        if success_count:
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"Sprawdzono: {success_count}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Zaimportowano: {success_count}"))
        if error_count:
            self.stdout.write(self.style.ERROR(f"Błędów: {error_count}"))
        if inconsistencies:
            self.stdout.write(self.style.WARNING("\nNiespójności:"))
            for msg in inconsistencies:
                self.stdout.write(self.style.WARNING(msg))

    def handle(self, *args, **options):
        client = self.get_client(
            options["app_id"],
            options["app_token"],
            options["base_url"],
            options["user_token"],
            verbose=options.get("verbosity", 1) > 1,
        )

        dry_run = options["dry_run"]

        # W trybie dry-run nie potrzebujemy jednostki
        default_jednostka = None
        if not dry_run:
            default_jednostka = get_validated_default_jednostka(
                jednostka_name=options["jednostka"]
            )

        success_count = 0
        error_count = 0
        inconsistencies = []

        def inconsistency_callback(inconsistency_type, message="", **kwargs):
            inconsistencies.append(f"  [{inconsistency_type}] {message}")

        for pbn_uid in options["pbn_uids"]:
            action = "Sprawdzam" if dry_run else "Importuję"
            self.stdout.write(f"\n{action}: {pbn_uid}")

            try:
                if dry_run:
                    success = self._dry_run_single_publication(pbn_uid, client)
                else:
                    success = self._import_single_publication(
                        pbn_uid,
                        client,
                        default_jednostka,
                        options,
                        inconsistency_callback,
                    )
                if success:
                    success_count += 1
                else:
                    error_count += 1

            except HttpException as e:
                self.stderr.write(
                    self.style.ERROR(f"  HTTP {e.status_code}: {e.content[:200]}")
                )
                error_count += 1

        self._print_summary(success_count, error_count, inconsistencies, dry_run)
