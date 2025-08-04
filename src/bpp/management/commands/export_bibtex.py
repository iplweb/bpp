"""
Django management command to export publications to BibTeX format.
"""
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from bpp.bibtex_export import export_to_bibtex
from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


class Command(BaseCommand):
    help = "Export publications to BibTeX format"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path. If not specified, output goes to stdout.",
        )

        parser.add_argument(
            "--year",
            "-y",
            type=int,
            help="Filter publications by year",
        )

        parser.add_argument(
            "--author",
            "-a",
            type=str,
            help="Filter publications by author name (searches in both nazwisko and imiona)",
        )

        parser.add_argument(
            "--type",
            "-t",
            choices=["ciagle", "zwarte", "all"],
            default="all",
            help="Type of publications to export (default: all)",
        )

        parser.add_argument(
            "--limit",
            "-l",
            type=int,
            help="Limit number of publications to export",
        )

        parser.add_argument(
            "--ids",
            nargs="+",
            type=int,
            help="Export specific publication IDs",
        )

    def handle(self, *args, **options):
        publications = []

        # Build queries based on options
        ciagle_q = Q()
        zwarte_q = Q()

        # Filter by year
        if options["year"]:
            ciagle_q &= Q(rok=options["year"])
            zwarte_q &= Q(rok=options["year"])

        # Filter by author
        if options["author"]:
            author_filter = Q(autorzy__nazwisko__icontains=options["author"]) | Q(
                autorzy__imiona__icontains=options["author"]
            )
            ciagle_q &= author_filter
            zwarte_q &= author_filter

        # Filter by specific IDs
        if options["ids"]:
            ciagle_q &= Q(id__in=options["ids"])
            zwarte_q &= Q(id__in=options["ids"])

        # Get publications based on type
        if options["type"] in ["ciagle", "all"]:
            ciagle_qs = Wydawnictwo_Ciagle.objects.filter(ciagle_q).distinct()
            if options["limit"] and options["type"] == "ciagle":
                ciagle_qs = ciagle_qs[: options["limit"]]
            publications.extend(list(ciagle_qs))

        if options["type"] in ["zwarte", "all"]:
            zwarte_qs = Wydawnictwo_Zwarte.objects.filter(zwarte_q).distinct()
            if options["limit"] and options["type"] == "zwarte":
                zwarte_qs = zwarte_qs[: options["limit"]]
            publications.extend(list(zwarte_qs))

        # Apply global limit if type is 'all'
        if options["limit"] and options["type"] == "all":
            publications = publications[: options["limit"]]

        if not publications:
            raise CommandError("No publications found matching the criteria.")

        # Generate BibTeX content
        self.stdout.write(f"Exporting {len(publications)} publications to BibTeX...")
        bibtex_content = export_to_bibtex(publications)

        # Output to file or stdout
        if options["output"]:
            try:
                with open(options["output"], "w", encoding="utf-8") as f:
                    f.write(bibtex_content)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully exported to {options["output"]}')
                )
            except OSError as e:
                raise CommandError(f"Error writing to file: {e}")
        else:
            sys.stdout.write(bibtex_content)

        self.stdout.write(
            self.style.SUCCESS(f"Export completed: {len(publications)} publications")
        )
