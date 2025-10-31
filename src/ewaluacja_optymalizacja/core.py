"""
Core optimization logic for evaluation optimization.

This module contains the main algorithms for solving the evaluation optimization problem
using constraint programming (CP-SAT solver from OR-Tools).
"""

import logging
import sys
import traceback
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum
from ortools.sat.python import cp_model
from tqdm import tqdm

from bpp import const
from bpp.models import Cache_Punktacja_Autora_Query, Dyscyplina_Naukowa
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    LiczbaNDlaUczelni,
)

logger = logging.getLogger(__name__)

# We'll scale slot numbers by 1000 for better precision (integers for CP-SAT)
SCALE = 1000


@dataclass(frozen=True)
class Pub:
    """Represents a publication with optimization-relevant data."""

    id: tuple  # (content_type_id, object_id) from rekord_id
    author: int  # autor_id
    kind: str  # "article" | "monography"
    points: float  # pkdaut from cache
    base_slots: float  # slot value from cache
    author_count: int  # number of authors with pinned disciplines
    jest_w_n: bool  # whether author is in liczba N (rodzaj_autora.jest_w_n)

    @property
    def efficiency(self) -> float:
        """Points per slot ratio for optimization"""
        return self.points / self.base_slots if self.base_slots > 0 else 0


def slot_units(p: Pub) -> int:
    """Convert float slots to scaled integer units for CP-SAT solver"""
    # Use round() for better precision with 2-decimal slot values
    return round(p.base_slots * SCALE)


def is_low_mono(p: Pub) -> bool:
    """Check if publication is a low-point monography (< 200 points)"""
    return p.kind == "monography" and p.points < 200


def solve_author_knapsack(
    author_pubs: list[Pub], max_slots: float, max_mono_slots: float
) -> list[Pub]:
    """
    Solve knapsack problem for a single author using dynamic programming.
    Returns list of selected publications that maximize points within slot constraints.
    """
    if not author_pubs:
        return []

    # Sort by efficiency (points/slot ratio) descending, then by author count ascending
    # This ensures that when efficiency is equal, works with fewer authors are prioritized
    sorted_pubs = sorted(author_pubs, key=lambda p: (-p.efficiency, p.author_count))

    # Use CP-SAT for single-author optimization with both constraints
    m = cp_model.CpModel()

    # Decision variables
    selected = {}
    for p in sorted_pubs:
        selected[p.id] = m.NewBoolVar(f"select_{p.id[0]}_{p.id[1]}")

    # Objective: maximize points
    m.Maximize(sum(p.points * selected[p.id] for p in sorted_pubs))

    # Constraint 1: Total slots
    m.Add(
        sum(int(p.base_slots * SCALE) * selected[p.id] for p in sorted_pubs)
        <= int(max_slots * SCALE)
    )

    # Constraint 2: Monography slots
    mono_pubs = [p for p in sorted_pubs if p.kind == "monography"]
    if mono_pubs:
        m.Add(
            sum(int(p.base_slots * SCALE) * selected[p.id] for p in mono_pubs)
            <= int(max_mono_slots * SCALE)
        )

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1  # Single thread for deterministic results
    status = solver.Solve(m)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return []

    # Return selected publications
    result = []
    for p in sorted_pubs:
        if solver.Value(selected[p.id]) == 1:
            result.append(p)

    return result


def generate_pub_data(dyscyplina_nazwa: str, verbose: bool = False) -> list[Pub]:
    """
    Generate publication data from cache_punktacja_autora table.

    Args:
        dyscyplina_nazwa: Name of the scientific discipline to filter by
        verbose: Show progress bar if True

    Returns:
        List of Pub objects with data from database
    """
    # Get discipline object
    try:
        dyscyplina = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina_nazwa)
    except Dyscyplina_Naukowa.DoesNotExist as e:
        raise ValueError(
            f"Discipline '{dyscyplina_nazwa}' not found in database"
        ) from e

    # Query cache data for years 2022-2025 and given discipline
    cache_entries = (
        Cache_Punktacja_Autora_Query.objects.filter(
            dyscyplina=dyscyplina,
            rekord__rok__gte=2022,
            rekord__rok__lte=2025,
        )
        .select_related(
            "autor",
            "rekord",
        )
        .exclude(pkdaut=0)  # Exclude publications with 0 points
        .exclude(slot__lt=Decimal("0.1"))  # Exclude publications with 0 slots
    )

    # Build a dictionary mapping autor_id to jest_w_n status
    # Query all authors' rodzaj_autora for this discipline
    autor_jest_w_n = {}
    autor_ids = cache_entries.values_list("autor_id", flat=True).distinct()

    for autor_id in autor_ids:
        record = (
            IloscUdzialowDlaAutoraZaCalosc.objects.filter(
                autor_id=autor_id,
                dyscyplina_naukowa=dyscyplina,
            )
            .select_related("rodzaj_autora")
            .order_by("-ilosc_udzialow")
            .first()
        )

        # Default to False if no record or no rodzaj_autora
        if record and record.rodzaj_autora:
            autor_jest_w_n[autor_id] = record.rodzaj_autora.jest_w_n
        else:
            autor_jest_w_n[autor_id] = False

    pubs = []
    iterator = tqdm(cache_entries) if verbose else cache_entries
    for entry in iterator:
        rekord = entry.rekord

        # Determine publication kind based on charakter_ogolny
        charakter_ogolny = rekord.charakter_formalny.charakter_ogolny
        if charakter_ogolny == const.CHARAKTER_OGOLNY_ARTYKUL:
            kind = "article"
        elif charakter_ogolny == const.CHARAKTER_OGOLNY_KSIAZKA:
            kind = "monography"
        else:
            # Skip other types (chapters, etc.)
            continue

        # Count authors with pinned disciplines
        author_count = rekord.original.autorzy_set.filter(
            dyscyplina_naukowa__isnull=False, przypieta=True
        ).count()

        pub = Pub(
            id=entry.rekord_id,  # This is already a tuple
            author=entry.autor_id,
            kind=kind,
            points=float(entry.pkdaut),
            base_slots=round(float(entry.slot), 2),  # Round to 2 decimal places
            author_count=author_count,
            jest_w_n=autor_jest_w_n.get(entry.autor_id, False),
        )
        pubs.append(pub)

    return pubs


class SolutionCallback(cp_model.CpSolverSolutionCallback):
    """Callback to report solver progress"""

    def __init__(self, variables, pubs, verbose=False):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.variables = variables
        self.pubs = pubs
        self.solution_count = 0
        self.verbose = verbose
        self.best_objective = 0

    def on_solution_callback(self):
        self.solution_count += 1
        current_objective = self.ObjectiveValue()

        if current_objective > self.best_objective:
            self.best_objective = current_objective
            if self.verbose:
                sys.stdout.write(
                    f"\rFound solution #{self.solution_count}: {int(current_objective)} points"
                )
                sys.stdout.flush()
            else:
                sys.stdout.write(".")
                sys.stdout.flush()


@dataclass
class OptimizationResults:
    """Container for optimization results"""

    dyscyplina_nazwa: str
    total_points: float
    total_slots: float
    total_publications: int
    low_mono_count: int
    low_mono_percentage: float
    authors: dict  # author_id -> {selected_pubs: list[Pub], limits: dict}
    all_pubs: list[Pub]  # All input publications
    validation_passed: bool


def _load_author_slot_limits(authors: list[int], dyscyplina_obj, log_func) -> dict:
    """
    Load per-author slot limits from database.

    Args:
        authors: List of author IDs
        dyscyplina_obj: Dyscyplina_Naukowa object
        log_func: Function to call for logging

    Returns:
        Dictionary mapping author_id to {"total": float, "mono": float}
    """
    log_func("Loading author slot limits from database...")
    author_slot_limits = {}
    custom_limit_count = 0

    for author_id in authors:
        # Aggregate slot limits across all rodzaj_autora types for this author
        aggregated = IloscUdzialowDlaAutoraZaCalosc.objects.filter(
            autor_id=author_id,
            dyscyplina_naukowa=dyscyplina_obj,
        ).aggregate(
            total_slots=Sum("ilosc_udzialow"),
            total_mono_slots=Sum("ilosc_udzialow_monografie"),
        )

        if aggregated["total_slots"] is not None:
            # Apply regulatory caps: max 4.0 total, max 2.0 monographs
            total = min(round(float(aggregated["total_slots"]), 2), 4.0)
            mono = min(round(float(aggregated["total_mono_slots"]), 2), 2.0)

            author_slot_limits[author_id] = {"total": total, "mono": mono}
            custom_limit_count += 1
        else:
            # Use default limits if not specified
            author_slot_limits[author_id] = {"total": 4.0, "mono": 2.0}

    log_func(f"Found custom slot limits for {custom_limit_count} authors")
    return author_slot_limits


def _run_phase1_per_author_optimization(
    pubs: list[Pub],
    authors: list[int],
    author_slot_limits: dict,
    verbose: bool,
    log_func,
) -> tuple[dict, float]:
    """
    Run Phase 1: Per-author optimization using knapsack algorithm.

    Args:
        pubs: List of all publications
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        verbose: Show detailed progress
        log_func: Function to call for logging

    Returns:
        Tuple of (author_selections dict, total_phase1_points)
    """
    log_func("=" * 80)
    log_func("PHASE 1: Per-author optimization")
    log_func("=" * 80)

    # Group publications by author
    pubs_by_author = {}
    for p in pubs:
        if p.author not in pubs_by_author:
            pubs_by_author[p.author] = []
        pubs_by_author[p.author].append(p)

    # Solve knapsack for each author
    author_selections = {}
    total_phase1_points = 0

    for author_id in authors:
        author_pubs = pubs_by_author.get(author_id, [])
        if not author_pubs:
            continue

        limits = author_slot_limits[author_id]
        if verbose:
            log_func(
                f"\nOptimizing for author {author_id}: {len(author_pubs)} publications"
            )
            log_func(
                f"  Limits: {limits['total']} total slots, {limits['mono']} mono slots"
            )

        # Solve knapsack for this author
        selected = solve_author_knapsack(author_pubs, limits["total"], limits["mono"])

        author_selections[author_id] = selected
        author_points = sum(p.points for p in selected)
        author_slots = sum(p.base_slots for p in selected)
        total_phase1_points += author_points

        if verbose:
            log_func(
                f"  Selected: {len(selected)} pubs, {author_points:.1f} points, {author_slots:.2f} slots"
            )

    log_func(f"\nPhase 1 complete: {total_phase1_points:.1f} total points")
    return author_selections, total_phase1_points


def _add_per_author_constraints(m, y, all_selected, authors, author_slot_limits):
    """Add per-author constraints to the CP model."""
    for author_id in authors:
        author_pubs = [p for p in all_selected if p.author == author_id]
        if not author_pubs:
            continue

        limits = author_slot_limits[author_id]

        # Total slots
        m.Add(
            sum(slot_units(p) * y[p.id] for p in author_pubs)
            <= int(limits["total"] * SCALE)
        )

        # Monography slots
        mono_pubs = [p for p in author_pubs if p.kind == "monography"]
        if mono_pubs:
            m.Add(
                sum(slot_units(p) * y[p.id] for p in mono_pubs)
                <= int(limits["mono"] * SCALE)
            )


def _apply_institution_constraints(
    author_selections: dict,
    authors: list[int],
    author_slot_limits: dict,
    liczba_n: float | None,
    log_func,
) -> tuple[list[Pub], float]:
    """
    Apply Phase 2: Institution-level constraints.

    Args:
        author_selections: Dictionary of selections from Phase 1
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        liczba_n: Institution-level slot limit
        log_func: Function to call for logging

    Returns:
        Tuple of (all_selected publications, total_points)
    """
    # Collect all selected publications
    all_selected = []
    for selections in author_selections.values():
        all_selected.extend(selections)

    log_func("=" * 80)
    log_func("PHASE 2: Institution-level constraints")
    log_func("=" * 80)

    # Count low-point monographies
    low_mono_selected = [p for p in all_selected if is_low_mono(p)]
    low_mono_percentage = (
        (100.0 * len(low_mono_selected) / len(all_selected)) if all_selected else 0
    )

    log_func(
        f"Low-point monographies: {len(low_mono_selected)}/{len(all_selected)} ({low_mono_percentage:.1f}%)"
    )

    # If we exceed 20% low-point monographies, we need to adjust
    if low_mono_percentage > 20.0 and len(low_mono_selected) > 0:
        log_func("Exceeds 20% limit - adjusting selection...", "WARNING")

        # Use CP-SAT to globally optimize while respecting all constraints
        m = cp_model.CpModel()

        # Decision variables for all pre-selected publications
        y = {p.id: m.NewBoolVar(f"y_{p.id[0]}_{p.id[1]}") for p in all_selected}

        # Objective: maximize points from pre-selected items
        m.Maximize(sum(p.points * y[p.id] for p in all_selected))

        # Per-author constraints
        _add_per_author_constraints(m, y, all_selected, authors, author_slot_limits)

        # Institution quota constraint: low-point monographies <= 20%
        low_mono_count = sum(y[p.id] for p in all_selected if is_low_mono(p))
        total_count = sum(y[p.id] for p in all_selected)
        m.Add(5 * low_mono_count <= total_count)  # 20% limit

        # Institution-level total slots constraint
        if liczba_n is not None:
            institution_total_slots = sum(slot_units(p) * y[p.id] for p in all_selected)
            m.Add(institution_total_slots <= int(liczba_n * SCALE))
            log_func(f"Institution constraint: total slots <= {liczba_n:.2f}")

        # Institution constraint: slots from outside-N authors <= 20%
        pubs_outside_n = [p for p in all_selected if not p.jest_w_n]
        if pubs_outside_n:
            outside_n_slots = sum(slot_units(p) * y[p.id] for p in pubs_outside_n)
            total_slots_expr = sum(slot_units(p) * y[p.id] for p in all_selected)
            # outside_n / total <= 0.2  =>  5 * outside_n <= total
            m.Add(5 * outside_n_slots <= total_slots_expr)
            log_func("Institution constraint: outside-N slots <= 20% of total")

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(m)

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            log_func("Could not satisfy institution constraints!", "ERROR")
            raise RuntimeError("Could not satisfy institution constraints!")

        # Update selections based on global optimization
        final_selected = []
        for p in all_selected:
            if solver.Value(y[p.id]) == 1:
                final_selected.append(p)

        all_selected = final_selected
        total_points = sum(p.points for p in all_selected)
        log_func(
            f"Adjusted selection: {len(all_selected)} publications, {total_points:.1f} points"
        )
    else:
        total_points = sum(p.points for p in all_selected)
        log_func("Institution constraints satisfied", "SUCCESS")

    return all_selected, total_points


def _validate_author_limits(
    all_selected: list[Pub], authors: list[int], author_slot_limits: dict, log_func
) -> bool:
    """
    Validate that no author exceeds their slot limits.

    Args:
        all_selected: List of all selected publications
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        log_func: Function to call for logging

    Returns:
        True if validation passed, False otherwise
    """
    log_func("=" * 80)
    log_func("VALIDATION: Checking slot limits")
    log_func("=" * 80)

    # Organize publications by author
    by_author: dict[int, list[Pub]] = {a: [] for a in authors}
    for p in all_selected:
        by_author[p.author].append(p)

    validation_passed = True
    for author_id in authors:
        chosen = by_author[author_id]
        if not chosen:
            continue

        total_slots = sum(p.base_slots for p in chosen)
        mono_slots = sum(p.base_slots for p in chosen if p.kind == "monography")
        limits = author_slot_limits[author_id]

        if (
            total_slots > limits["total"] + 0.01
        ):  # Epsilon for floating point arithmetic
            log_func(
                f"Author {author_id}: {total_slots:.2f} slots > {limits['total']} limit!",
                "ERROR",
            )
            validation_passed = False

        if mono_slots > limits["mono"] + 0.01:  # Epsilon for floating point arithmetic
            log_func(
                f"Author {author_id}: {mono_slots:.2f} mono slots > {limits['mono']} limit!",
                "ERROR",
            )
            validation_passed = False

    if validation_passed:
        log_func("✓ All slot limits satisfied", "SUCCESS")
    else:
        log_func("✗ Validation failed - slot limits exceeded!", "ERROR")

    return validation_passed


def _build_optimization_results(
    dyscyplina_nazwa: str,
    all_selected: list[Pub],
    pubs: list[Pub],
    authors: list[int],
    author_slot_limits: dict,
    total_points: float,
    validation_passed: bool,
) -> OptimizationResults:
    """
    Build the final OptimizationResults object.

    Args:
        dyscyplina_nazwa: Name of the discipline
        all_selected: List of all selected publications
        pubs: List of all input publications
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        total_points: Total points from optimization
        validation_passed: Whether validation passed

    Returns:
        OptimizationResults object
    """
    # Organize publications by author
    by_author: dict[int, list[Pub]] = {a: [] for a in authors}
    for p in all_selected:
        by_author[p.author].append(p)

    # Calculate final statistics
    total_slots_used = sum(p.base_slots for p in all_selected)
    sel_low = len([p for p in all_selected if is_low_mono(p)])
    share = (100.0 * sel_low / len(all_selected)) if all_selected else 0.0

    # Build author results
    author_results = {}
    for author_id in authors:
        chosen = by_author[author_id]
        if not chosen:
            continue
        author_results[author_id] = {
            "selected_pubs": chosen,
            "limits": author_slot_limits[author_id],
        }

    return OptimizationResults(
        dyscyplina_nazwa=dyscyplina_nazwa,
        total_points=total_points,
        total_slots=total_slots_used,
        total_publications=len(all_selected),
        low_mono_count=sel_low,
        low_mono_percentage=share,
        authors=author_results,
        all_pubs=pubs,
        validation_passed=validation_passed,
    )


def solve_discipline(
    dyscyplina_nazwa: str,
    verbose: bool = False,
    log_callback=None,
    liczba_n: float | None = None,
) -> OptimizationResults:
    """
    Solve optimization for a single discipline.

    Args:
        dyscyplina_nazwa: Name of the scientific discipline
        verbose: Show detailed progress
        log_callback: Optional function to call for logging (receives message string)
        liczba_n: Institution-level slot limit for this discipline (from LiczbaNDlaUczelni)

    Returns:
        OptimizationResults object with complete results
    """

    def log(msg: str, style: str | None = None):
        """Helper to log messages"""
        if log_callback:
            log_callback(msg, style)
        elif verbose:
            print(msg)

    log(f"Loading publications for discipline: {dyscyplina_nazwa}")

    # Generate publication data from database
    try:
        pubs = generate_pub_data(dyscyplina_nazwa, verbose=verbose)
    except ValueError as e:
        log(str(e), "ERROR")
        raise

    if not pubs:
        log(
            f"No publications found for discipline '{dyscyplina_nazwa}' in years 2022-2025",
            "WARNING",
        )
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

    log(f"Found {len(pubs)} publications")

    # Get unique authors
    authors = sorted({p.author for p in pubs})
    log(f"Found {len(authors)} unique authors")

    # Get discipline object for loading slot limits
    dyscyplina_obj = Dyscyplina_Naukowa.objects.get(nazwa=dyscyplina_nazwa)

    # Load per-author slot limits
    author_slot_limits = _load_author_slot_limits(authors, dyscyplina_obj, log)

    # PHASE 1: Solve per-author knapsack problems
    author_selections, _ = _run_phase1_per_author_optimization(
        pubs, authors, author_slot_limits, verbose, log
    )

    # PHASE 2: Apply institution-level constraints
    all_selected, total_points = _apply_institution_constraints(
        author_selections, authors, author_slot_limits, liczba_n, log
    )

    # Validation: Check that no author exceeds their limits
    validation_passed = _validate_author_limits(
        all_selected, authors, author_slot_limits, log
    )

    log(f"\nTotal points: {int(total_points)}", "SUCCESS")

    # Build and return results
    return _build_optimization_results(
        dyscyplina_nazwa,
        all_selected,
        pubs,
        authors,
        author_slot_limits,
        total_points,
        validation_passed,
    )


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
            f"No disciplines found for university {uczelnia} with liczba_n >= {min_liczba_n}"
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
