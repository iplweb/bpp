"""
Management command to solve optimization for all disciplines in a university.
"""

from datetime import datetime
from decimal import Decimal

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Dyscyplina_Naukowa, Uczelnia
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_optymalizacja.core import is_low_mono, solve_uczelnia
from ewaluacja_optymalizacja.models import (
    OptimizationAuthorResult,
    OptimizationPublication,
    OptimizationRun,
)


class Command(BaseCommand):
    help = """Solve evaluation optimization for all disciplines in a university.

    Processes all disciplines with liczba_n >= min_liczba_n (default: 12)
    and saves results to the database.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--uczelnia",
            type=int,
            default=None,
            help="University ID (if not specified, uses first available)",
        )
        parser.add_argument(
            "--min-liczba-n",
            type=int,
            default=12,
            help="Minimum liczba N threshold (default: 12)",
        )
        parser.add_argument(
            "--save-to-db",
            action="store_true",
            default=True,
            help="Save results to database (default: True)",
        )

    def handle(self, uczelnia, min_liczba_n, save_to_db, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("SOLVING OPTIMIZATION FOR UNIVERSITY")
        self.stdout.write("=" * 80)

        # Get university
        if uczelnia:
            try:
                uczelnia_obj = Uczelnia.objects.get(pk=uczelnia)
            except Uczelnia.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"University with ID {uczelnia} not found")
                )
                return
        else:
            uczelnia_obj = Uczelnia.objects.first()
            if not uczelnia_obj:
                self.stdout.write(self.style.ERROR("No university found in database"))
                return

        self.stdout.write(f"University: {uczelnia_obj}")
        self.stdout.write(f"Minimum liczba N: {min_liczba_n}")
        self.stdout.write(f"Save to database: {save_to_db}")
        self.stdout.write("")

        # Process disciplines
        results_count = 0
        errors_count = 0

        for dyscyplina_nazwa, results in solve_uczelnia(
            uczelnia_id=uczelnia_obj.pk, min_liczba_n=min_liczba_n
        ):
            try:
                if save_to_db:
                    self._save_results(
                        results, dyscyplina_nazwa, uczelnia_obj=uczelnia_obj
                    )
                results_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error saving {dyscyplina_nazwa}: {e}")
                )
                errors_count += 1
                continue

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Processed disciplines: {results_count}")
        if errors_count:
            self.stdout.write(self.style.WARNING(f"Errors: {errors_count}"))
        self.stdout.write(self.style.SUCCESS("Optimization complete!"))

    @transaction.atomic
    def _save_results(self, results, dyscyplina_nazwa, uczelnia_obj):
        """Save optimization results to database"""
        dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina_nazwa)

        # Usuń stare optymalizacje dla tej dyscypliny
        OptimizationRun.objects.filter(dyscyplina_naukowa=dyscyplina_obj).delete()

        # Create OptimizationRun
        opt_run = OptimizationRun.objects.create(
            dyscyplina_naukowa=dyscyplina_obj,
            uczelnia=uczelnia_obj,
            status="completed",
            total_points=Decimal(str(results.total_points)),
            total_slots=Decimal(str(results.total_slots)),
            total_publications=results.total_publications,
            low_mono_count=results.low_mono_count,
            low_mono_percentage=Decimal(str(results.low_mono_percentage)),
            validation_passed=results.validation_passed,
            finished_at=datetime.now(),
        )

        # Save author results
        for author_id, author_data in results.authors.items():
            selected_pubs = author_data["selected_pubs"]
            limits = author_data["limits"]

            # Get rodzaj_autora for this author (może być wiele rekordów - bierzemy pierwszy)
            record = (
                IloscUdzialowDlaAutoraZaCalosc.objects.filter(
                    autor_id=author_id, dyscyplina_naukowa=dyscyplina_obj
                )
                .order_by("-ilosc_udzialow")
                .first()
            )
            rodzaj_autora = record.rodzaj_autora if record else None

            total_points = sum(p.points for p in selected_pubs)
            total_slots = sum(p.base_slots for p in selected_pubs)
            mono_slots = sum(
                p.base_slots for p in selected_pubs if p.kind == "monography"
            )

            author_result = OptimizationAuthorResult.objects.create(
                optimization_run=opt_run,
                autor_id=author_id,
                rodzaj_autora=rodzaj_autora,
                total_points=Decimal(str(total_points)),
                total_slots=Decimal(str(total_slots)),
                mono_slots=Decimal(str(mono_slots)),
                slot_limit_total=Decimal(str(limits["total"])),
                slot_limit_mono=Decimal(str(limits["mono"])),
            )

            # Save publications for this author
            for pub in selected_pubs:
                OptimizationPublication.objects.create(
                    author_result=author_result,
                    rekord_id=pub.id,
                    kind=pub.kind,
                    points=Decimal(str(pub.points)),
                    slots=Decimal(str(pub.base_slots)),
                    is_low_mono=is_low_mono(pub),
                    author_count=pub.author_count,
                )

        self.stdout.write(
            self.style.SUCCESS(f"✓ {dyscyplina_nazwa}: Saved run #{opt_run.pk}")
        )
