"""
Core optimization logic for evaluation optimization.

This module contains the main algorithms for solving the evaluation optimization problem
using constraint programming (CP-SAT solver from OR-Tools).
"""

import logging
import os
import traceback

from bpp.models import Dyscyplina_Naukowa
from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

from .data_loader import generate_pub_data, load_author_slot_limits
from .data_structures import (
    SCALE,
    OptimizationResults,
    Pub,
    is_low_mono,
    slot_units,
)
from .optimization_phases import (
    PinningCandidate,
    analyze_pinning_candidates,
    apply_institution_constraints,
    build_optimization_results,
    run_phase1_per_author_optimization,
    run_single_phase_optimization,
    validate_author_limits,
)
from .solver import SolutionCallback, solve_author_knapsack

logger = logging.getLogger(__name__)


def _empty_results(dyscyplina_nazwa: str) -> "OptimizationResults":
    """Return empty OptimizationResults for a discipline with no publications."""
    return OptimizationResults(
        dyscyplina_nazwa=dyscyplina_nazwa,
        total_points=0,
        total_slots=0,
        total_publications=0,
        low_mono_count=0,
        low_mono_percentage=0,
        authors={},
        all_pubs=[],
        validation_passed=True,
    )


def _run_two_phase_optimization(
    pubs: list[Pub],
    authors: list[int],
    author_slot_limits: dict,
    liczba_n: float | None,
    verbose: bool,
    log,
) -> tuple[list[Pub], float, bool, float | None, float | None]:
    """Run two-phase optimization: per-author, then institution constraints."""
    # PHASE 1: Solve per-author knapsack problems
    author_selections, _, phase1_optimal = run_phase1_per_author_optimization(
        pubs, authors, author_slot_limits, verbose, log
    )

    # Collect phase1 selected IDs for hints in phase 2
    phase1_selected_ids = set()
    for selections in author_selections.values():
        for p in selections:
            phase1_selected_ids.add(p.id)

    # PHASE 2: Apply institution-level constraints with ALL publications
    # (IMPROVED: Now passes all publications and uses phase1 as hints)
    (
        all_selected,
        total_points,
        phase2_optimal,
        gap_percent,
        best_bound,
    ) = apply_institution_constraints(
        pubs,  # ALL publications, not just phase1 selected
        phase1_selected_ids,  # IDs from phase1 for hints
        authors,
        author_slot_limits,
        liczba_n,
        log,
    )

    # Overall optimality: both phases must be optimal
    is_optimal = phase1_optimal and phase2_optimal

    return all_selected, total_points, is_optimal, gap_percent, best_bound


__all__ = [
    # Data structures
    "SCALE",
    "Pub",
    "OptimizationResults",
    "slot_units",
    "is_low_mono",
    # Data loading
    "generate_pub_data",
    "load_author_slot_limits",
    # Solver
    "solve_author_knapsack",
    "SolutionCallback",
    # Optimization phases
    "run_phase1_per_author_optimization",
    "apply_institution_constraints",
    "validate_author_limits",
    "build_optimization_results",
    "run_single_phase_optimization",
    # Phase 3: Capacity-based pinning
    "PinningCandidate",
    "analyze_pinning_candidates",
    "apply_pinning_candidates",
    # Main entry points
    "solve_discipline",
    "solve_uczelnia",
]


def solve_discipline(
    dyscyplina_nazwa: str,
    verbose: bool = False,
    log_callback=None,
    liczba_n: float | None = None,
    algorithm_mode: str = "two-phase",
) -> OptimizationResults:
    """
    Solve optimization for a single discipline.

    Args:
        dyscyplina_nazwa: Name of the scientific discipline
        verbose: Show detailed progress
        log_callback: Optional function to call for logging (receives message string)
        liczba_n: Institution-level slot limit (3N - sankcje, used directly as max slots)
        algorithm_mode: "two-phase" (default) or "single-phase"
            - "two-phase": Phase 1 per-author optimization, Phase 2 institution constraints
            - "single-phase": Global CP-SAT with all constraints from start

    Returns:
        OptimizationResults object with complete results
    """

    def log(msg: str, style: str | None = None):
        """Helper to log messages"""
        if log_callback:
            log_callback(msg, style)
        elif verbose:
            print(msg)

    # Validate algorithm_mode parameter
    if algorithm_mode not in ["two-phase", "single-phase"]:
        raise ValueError(
            f"Invalid algorithm_mode: '{algorithm_mode}'. "
            "Must be 'two-phase' or 'single-phase'."
        )

    log(f"Algorithm mode: {algorithm_mode}")

    # Log solver configuration
    cpu_count = os.cpu_count() or 8
    if algorithm_mode == "single-phase":
        log(
            f"Solver config: {cpu_count} workers, timeout 30 min (1800s), THOROUGH mode"
        )
    else:
        log(
            f"Solver config: {cpu_count} workers, per-author: no limit, "
            "institution timeout 30 min, THOROUGH mode"
        )

    log(f"Loading publications for discipline: {dyscyplina_nazwa}")

    # Generate publication data from database
    try:
        pubs = generate_pub_data(dyscyplina_nazwa, verbose=verbose)
    except ValueError as e:
        log(str(e), "ERROR")
        raise

    if not pubs:
        log(
            f"No publications found for discipline '{dyscyplina_nazwa}' "
            "in years 2022-2025",
            "WARNING",
        )
        return _empty_results(dyscyplina_nazwa)

    log(f"Found {len(pubs)} publications")

    # Get unique authors
    authors = sorted({p.author for p in pubs})
    log(f"Found {len(authors)} unique authors")

    # Get discipline object for loading slot limits
    dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina_nazwa)

    # Load per-author slot limits
    author_slot_limits = load_author_slot_limits(authors, dyscyplina_obj, log)

    # Run optimization based on selected algorithm mode
    gap_percent = None
    best_bound = None

    if algorithm_mode == "single-phase":
        # Single-phase: Global CP-SAT with all constraints from start
        (
            all_selected,
            total_points,
            is_optimal,
            gap_percent,
            best_bound,
        ) = run_single_phase_optimization(
            pubs, authors, author_slot_limits, liczba_n, verbose, log
        )
    else:
        # Two-phase: Per-author optimization, then institution constraints
        (
            all_selected,
            total_points,
            is_optimal,
            gap_percent,
            best_bound,
        ) = _run_two_phase_optimization(
            pubs, authors, author_slot_limits, liczba_n, verbose, log
        )

    # Validation: Check that no author exceeds their limits
    validation_passed = validate_author_limits(
        all_selected, authors, author_slot_limits, log
    )

    opt_status = "OPTIMAL" if is_optimal else "FEASIBLE (sub-optimal)"
    log(f"\nTotal points: {int(total_points)} ({opt_status})", "SUCCESS")

    # Build and return results
    return build_optimization_results(
        dyscyplina_nazwa,
        all_selected,
        pubs,
        authors,
        author_slot_limits,
        total_points,
        validation_passed,
        is_optimal,
        optimality_gap_percent=gap_percent,
        best_bound=best_bound,
    )


def apply_pinning_candidates(
    candidates: list[PinningCandidate],
    dyscyplina_obj: Dyscyplina_Naukowa,
    log_func,
    dry_run: bool = True,
) -> dict:
    """
    Apply pinning decisions for identified candidates.

    This function pins authors back to publications where they were previously unpinned,
    allowing them to utilize free slots.

    Args:
        candidates: List of PinningCandidate objects to process
        dyscyplina_obj: Dyscyplina_Naukowa object
        log_func: Function for logging
        dry_run: If True, show what would happen without making changes

    Returns:
        Dictionary with results:
        {
            'pinned_count': int,
            'errors': list[str],
            'dry_run': bool,
        }
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction

    from bpp.models import (
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte,
        Wydawnictwo_Zwarte_Autor,
    )
    from bpp.models.sloty.core import IPunktacjaCacher

    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    pinned_count = 0
    errors = []

    log_func("=" * 80)
    if dry_run:
        log_func("PHASE 3 DRY-RUN: Would apply the following pinning changes")
    else:
        log_func("PHASE 3: Applying pinning changes")
    log_func("=" * 80)

    with transaction.atomic():
        sid = transaction.savepoint() if dry_run else None

        for candidate in candidates:
            content_type_id, object_id = candidate.publication_id

            # Determine model based on content type
            if content_type_id == ct_ciagle.id:
                AutorModel = Wydawnictwo_Ciagle_Autor  # noqa: N806
                RekordModel = Wydawnictwo_Ciagle  # noqa: N806
            elif content_type_id == ct_zwarte.id:
                AutorModel = Wydawnictwo_Zwarte_Autor  # noqa: N806
                RekordModel = Wydawnictwo_Zwarte  # noqa: N806
            else:
                logger.warning(
                    f"Unknown content_type_id {content_type_id} for "
                    f"publication {candidate.publication_id}"
                )
                continue

            try:
                # Update przypieta to True
                updated = AutorModel.objects.filter(
                    rekord_id=object_id,
                    autor_id=candidate.author_id,
                    dyscyplina_naukowa=dyscyplina_obj,
                    przypieta=False,
                ).update(przypieta=True)

                if updated > 0:
                    pinned_count += updated
                    log_func(
                        f"  Pinned author {candidate.author_id} to publication "
                        f"{object_id}: {candidate.points:.1f} pts, "
                        f"{candidate.slots:.2f} slots"
                    )

                    # Rebuild cache for this publication
                    if not dry_run:
                        rekord = RekordModel.objects.get(pk=object_id)
                        cacher = IPunktacjaCacher(rekord)
                        cacher.removeEntries()
                        cacher.rebuildEntries()

            except Exception as e:
                error_msg = (
                    f"Error pinning author {candidate.author_id} "
                    f"to publication {object_id}: {e}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        if dry_run and sid is not None:
            transaction.savepoint_rollback(sid)
            log_func(
                f"\nDry-run: rolled back transaction, would pin {pinned_count} "
                "author assignments"
            )
        else:
            log_func(f"\nApplied pinning to {pinned_count} author assignments")

    return {
        "pinned_count": pinned_count,
        "errors": errors,
        "dry_run": dry_run,
    }


def solve_uczelnia(uczelnia_id: int | None = None, min_liczba_n: int = 12):
    """
    Solve optimization for all disciplines in university with liczba_n >= min_liczba_n.

    Args:
        uczelnia_id: University ID (if None, uses first available)
        min_liczba_n: Minimum liczba N threshold (default: 12)

    Yields:
        (dyscyplina_nazwa, OptimizationResults) tuples
    """
    from bpp.models import Uczelnia

    # Get university
    if uczelnia_id:
        uczelnia = Uczelnia.objects.get(pk=uczelnia_id)
    else:
        uczelnia = Uczelnia.objects.first()
        if not uczelnia:
            raise ValueError("No university found in database")

    # Get disciplines with liczba_n >= min_liczba_n
    liczba_n_query = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=min_liczba_n
    ).select_related("dyscyplina_naukowa")

    disciplines = list(liczba_n_query)

    if not disciplines:
        print(
            f"No disciplines found for university {uczelnia} "
            f"with liczba_n >= {min_liczba_n}"
        )
        return

    print(f"Processing {len(disciplines)} disciplines for {uczelnia}")
    print(f"Disciplines with liczba_n >= {min_liczba_n}")
    print("=" * 80)

    # Process each discipline
    for liczba_n_obj in disciplines:
        dyscyplina = liczba_n_obj.dyscyplina_naukowa
        logger.info(f"\n{'=' * 80}")
        logger.info(
            f"Processing: {dyscyplina.nazwa} (liczba_n={liczba_n_obj.liczba_n})"
        )
        logger.info(f"{'=' * 80}")

        try:
            results = solve_discipline(
                dyscyplina.nazwa,
                verbose=False,
                liczba_n=float(liczba_n_obj.liczba_n),
            )
            yield (dyscyplina.nazwa, results)
        except Exception as e:
            # Log full traceback for debugging
            tb = traceback.format_exc()
            logger.error(
                f"ERROR processing {dyscyplina.nazwa}: {type(e).__name__}: {e}\n"
                f"Full traceback:\n{tb}"
            )
            # Re-raise to let caller decide how to handle
            raise
