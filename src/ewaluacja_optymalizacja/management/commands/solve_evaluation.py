"""Management command: solve evaluation optimization for a single discipline.

The actual work is delegated to functions under
``ewaluacja_optymalizacja.solve_helpers``; this module is a thin
orchestrator. Django identifies management commands by the file name,
so the file must remain a module (not a package) and must continue to
expose a ``Command`` class.
"""

import logging

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Dyscyplina_Naukowa, Uczelnia
from bpp.util import zaloguj_polkniety_wyjatek
from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from ewaluacja_optymalizacja.core import solve_discipline
from ewaluacja_optymalizacja.solve_helpers import (
    display_author_results,
    display_institution_statistics,
    find_unselected_multi_author_pubs,
    handle_capacity_based_unpinning,
    handle_phase3_pinning,
    handle_unpinning,
    load_author_names_and_records,
    save_optimization_to_database,
    save_results_to_json_file,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Solve evaluation optimization problem using CP-SAT solver.

    This command finds the optimal selection of publications for evaluation
    considering constraints on slots per author and institution-wide quotas.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "dyscyplina",
            type=str,
            help='Scientific discipline name (e.g., "nauki medyczne")',
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output file path for results (JSON format)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            default=False,
            help="Show detailed progress during solving",
        )
        parser.add_argument(
            "--unpin-not-selected",
            action="store_true",
            default=False,
            help=(
                "Unpin disciplines for authors in publications that were not "
                "selected for reporting"
            ),
        )
        parser.add_argument(
            "--rerun-after-unpin",
            action="store_true",
            default=False,
            help=(
                "Re-run the optimization after unpinning "
                "(use with --unpin-not-selected)"
            ),
        )
        parser.add_argument(
            "--algorithm-mode",
            type=str,
            default="two-phase",
            choices=["two-phase", "single-phase"],
            help='Algorithm mode: "two-phase" (default) or "single-phase"',
        )
        parser.add_argument(
            "--show-publications",
            action="store_true",
            default=False,
            help="Show detailed publication list per author at the end",
        )
        parser.add_argument(
            "--analyze-unpinning",
            action="store_true",
            default=False,
            help=(
                "Analyze optimal unpinning based on capacity rule, show recommendations"
            ),
        )
        parser.add_argument(
            "--auto-unpin",
            action="store_true",
            default=False,
            help="Apply capacity-based unpinning before optimization (with preview)",
        )
        parser.add_argument(
            "--analyze-pinning",
            action="store_true",
            default=False,
            help=(
                "After optimization, analyze which unpinned authors could be "
                "re-pinned to utilize free slots (Phase 3 analysis only, "
                "no changes)"
            ),
        )
        parser.add_argument(
            "--enable-pinning",
            action="store_true",
            default=False,
            help=(
                "Apply Phase 3 capacity-based pinning after optimization: "
                "re-pin authors who have free slots to unselected publications"
            ),
        )

    @transaction.atomic
    def handle(  # noqa: C901
        self,
        dyscyplina,
        output,
        verbose,
        unpin_not_selected,
        rerun_after_unpin,
        algorithm_mode,
        show_publications,
        analyze_unpinning,
        auto_unpin,
        analyze_pinning,
        enable_pinning,
        *args,
        **options,
    ):
        def log_callback(msg, style=None):
            if style == "ERROR":
                self.stdout.write(self.style.ERROR(msg))
            elif style == "WARNING":
                self.stdout.write(self.style.WARNING(msg))
            elif style == "SUCCESS":
                self.stdout.write(self.style.SUCCESS(msg))
            else:
                self.stdout.write(msg)

        liczba_n = self._lookup_liczba_n(dyscyplina)

        # Pre-optimization: capacity-based unpinning analysis / application
        if analyze_unpinning or auto_unpin:
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            handle_capacity_based_unpinning(
                self.stdout,
                self.style,
                dyscyplina_obj,
                dry_run=not auto_unpin,
            )

            if analyze_unpinning and not auto_unpin:
                self.stdout.write(
                    self.style.WARNING(
                        "\nAnalysis complete. Use --auto-unpin to apply changes "
                        "and run optimization."
                    )
                )
                return

        self.stdout.write(f"Using algorithm mode: {algorithm_mode}")
        try:
            results = solve_discipline(
                dyscyplina_nazwa=dyscyplina,
                verbose=verbose,
                log_callback=log_callback,
                liczba_n=liczba_n,
                algorithm_mode=algorithm_mode,
            )
        except Exception as e:
            zaloguj_polkniety_wyjatek(
                f"Optymalizacja ewaluacji dla dyscypliny '{dyscyplina}' "
                "nie powiodła się",
                logger=logger,
                do_rollbar=False,
            )
            self.stdout.write(self.style.ERROR(f"Optimization failed: {e}"))
            return

        if not results.all_pubs:
            self.stdout.write(
                self.style.WARNING(
                    f"No publications found for discipline '{dyscyplina}'"
                )
            )
            return

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("Saving results to database...")
        self.stdout.write("=" * 80)

        save_optimization_to_database(self.stdout, self.style, results, dyscyplina)

        (
            authors,
            by_author,
            all_selected,
            author_names,
            rekords,
        ) = load_author_names_and_records(results)

        author_slot_limits = {
            author_id: data["limits"] for author_id, data in results.authors.items()
        }
        total_points = results.total_points

        if show_publications:
            display_author_results(
                self.stdout, authors, by_author, author_names, rekords, results
            )
        display_institution_statistics(self.stdout, all_selected, total_points)

        sorted_unselected = find_unselected_multi_author_pubs(
            self.stdout,
            results,
            all_selected,
            by_author,
            author_names,
            author_slot_limits,
            rekords,
        )

        if output:
            save_results_to_json_file(
                self.stdout,
                self.style,
                output,
                dyscyplina,
                total_points,
                all_selected,
                authors,
                by_author,
                author_names,
                rekords,
                sorted_unselected,
                author_slot_limits,
            )

        if analyze_pinning or enable_pinning:
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            handle_phase3_pinning(
                self.stdout,
                self.style,
                results,
                all_selected,
                author_slot_limits,
                dyscyplina_obj,
                log_callback,
                dry_run=not enable_pinning,
                rerun_after_pinning=enable_pinning,
                algorithm_mode=algorithm_mode,
                verbose=verbose,
            )

        if unpin_not_selected:
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            handle_unpinning(
                self.stdout,
                self.style,
                all_selected,
                results.all_pubs,
                dyscyplina_obj,
                rerun_after_unpin,
                dyscyplina,
                output,
                verbose,
                algorithm_mode,
            )

    def _lookup_liczba_n(self, dyscyplina):
        """Look up the institutional N-limit (3N - sankcje) for the discipline.

        Logs a SUCCESS or WARNING message via ``self.stdout`` and
        returns ``float`` or ``None`` when no limit is configured.
        """
        try:
            uczelnia = Uczelnia.objects.first()
            dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina)
            if uczelnia and dyscyplina_obj:
                liczba_n_obj = LiczbaNDlaUczelni.objects.get(
                    uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina_obj
                )
                liczba_n = float(liczba_n_obj.liczba_n_ostateczna)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Found for {dyscyplina}: N={liczba_n_obj.liczba_n}, "
                        f"sankcje={liczba_n_obj.sankcje}, "
                        f"3×N - sankcje = {liczba_n}"
                    )
                )
                return liczba_n
        except (Dyscyplina_Naukowa.DoesNotExist, LiczbaNDlaUczelni.DoesNotExist):
            self.stdout.write(
                self.style.WARNING(
                    f"No liczba_n found for discipline '{dyscyplina}'. "
                    "Institution constraint will not be applied."
                )
            )
        return None
