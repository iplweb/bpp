"""
Optimization phase functions for evaluation optimization.

This module contains the phase 1 (per-author) and phase 2 (institution-level)
optimization functions, as well as validation and result building functions.
"""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .data_structures import SCALE, OptimizationResults, Pub, is_low_mono, slot_units
from .solver import SolutionCallback, configure_solver, solve_author_knapsack


def run_phase1_per_author_optimization(
    pubs: list[Pub],
    authors: list[int],
    author_slot_limits: dict,
    verbose: bool,
    log_func,
) -> tuple[dict, float, bool]:
    """
    Run Phase 1: Per-author optimization using knapsack algorithm.

    Args:
        pubs: List of all publications
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        verbose: Show detailed progress
        log_func: Function to call for logging

    Returns:
        Tuple of (author_selections dict, total_phase1_points, all_optimal)
        all_optimal is True if all per-author solvers found OPTIMAL solutions
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
    all_optimal = True

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
        selected, is_optimal = solve_author_knapsack(
            author_pubs, limits["total"], limits["mono"]
        )
        if not is_optimal:
            all_optimal = False

        author_selections[author_id] = selected
        author_points = sum(p.points for p in selected)
        author_slots = sum(p.base_slots for p in selected)
        total_phase1_points += author_points

        if verbose:
            opt_status = "OPTIMAL" if is_optimal else "FEASIBLE"
            log_func(
                f"  Selected: {len(selected)} pubs, "
                f"{author_points:.1f} points, {author_slots:.2f} slots ({opt_status})"
            )

    log_func(f"\nPhase 1 complete: {total_phase1_points:.1f} total points")
    return author_selections, total_phase1_points, all_optimal


def _add_per_author_constraints(m, y, pubs, authors, author_slot_limits):
    """Add per-author constraints to the CP model."""
    for author_id in authors:
        author_pubs = [p for p in pubs if p.author == author_id]
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


def _calculate_optimality_gap(solver) -> tuple[float | None, float | None]:
    """
    Calculate optimality gap from solver results.

    Returns:
        Tuple of (gap_percent, best_bound) or (None, None) if not available.
    """
    try:
        best_bound = solver.BestObjectiveBound()
        obj_value = solver.ObjectiveValue()

        if best_bound > 0:
            gap_percent = ((best_bound - obj_value) / best_bound) * 100
            return gap_percent, best_bound
    except Exception:
        pass
    return None, None


def apply_institution_constraints(  # noqa: C901
    all_pubs: list[Pub],
    phase1_selected_ids: set,
    authors: list[int],
    author_slot_limits: dict,
    liczba_n: float | None,
    log_func,
) -> tuple[list[Pub], float, bool, float | None, float | None]:
    """
    Apply Phase 2: Institution-level constraints using ALL publications.

    CRITICAL FIX: This function now receives ALL publications (not just phase1 selected)
    and uses phase1 selections as hints for warm-starting. This allows the solver to
    find better global solutions by considering publications that phase1 rejected
    for individual authors but might be better globally.

    Args:
        all_pubs: List of ALL publications (not just phase1 selected)
        phase1_selected_ids: Set of (content_type_id, object_id) tuples selected in phase1
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        liczba_n: Institution-level slot limit (3N - sankcje, used directly)
        log_func: Function to call for logging

    Returns:
        Tuple of (selected publications, total_points, is_optimal, gap_percent, best_bound)
        is_optimal is True if solver found OPTIMAL solution
        gap_percent and best_bound may be None if not available
    """
    # Get phase1 selections for statistics
    phase1_selected = [p for p in all_pubs if p.id in phase1_selected_ids]

    log_func("=" * 80)
    log_func("PHASE 2: Institution-level constraints (IMPROVED)")
    log_func("=" * 80)
    log_func(
        f"Phase 1 selected: {len(phase1_selected)} publications, "
        f"Total available: {len(all_pubs)} publications"
    )

    # Count low-point monographies in phase1 selection
    low_mono_selected = [p for p in phase1_selected if is_low_mono(p)]
    low_mono_percentage = (
        (100.0 * len(low_mono_selected) / len(phase1_selected))
        if phase1_selected
        else 0
    )

    log_func(
        f"Phase 1 LOW-MONO: {len(low_mono_selected)}/{len(phase1_selected)} "
        f"({low_mono_percentage:.1f}%)"
    )

    # Calculate total slots for Phase 1 result
    total_slots = sum(p.base_slots for p in phase1_selected)

    # Calculate outside-N slots percentage
    outside_n_slots = sum(p.base_slots for p in phase1_selected if not p.jest_w_n)
    outside_n_percentage = (
        (100.0 * outside_n_slots / total_slots) if total_slots > 0 else 0
    )

    log_func(
        f"Phase 1 outside-N slots: {outside_n_slots:.2f}/{total_slots:.2f} "
        f"({outside_n_percentage:.1f}%)"
    )

    # Check if slot limit constraint is violated
    exceeds_limit = False
    if liczba_n is not None:
        max_slots = liczba_n
        log_func(f"Phase 1 slots vs limit: {total_slots:.2f} / {max_slots:.2f}")
        if total_slots > max_slots:
            exceeds_limit = True
            log_func(
                f"Exceeds slot limit by {total_slots - max_slots:.2f} slots", "WARNING"
            )

    # Check if any institution constraint is violated
    needs_adjustment = (
        (low_mono_percentage > 20.0 and len(low_mono_selected) > 0)
        or exceeds_limit
        or outside_n_percentage > 20.0
    )

    # IMPROVED: Always run global optimization in phase 2 to potentially find
    # better solutions, even if phase 1 satisfies constraints
    # The phase 1 results are used as hints for faster convergence
    log_func("Running global optimization with all publications...")
    if needs_adjustment:
        log_func("Institution constraints violated - must adjust selection", "WARNING")
        if low_mono_percentage > 20.0 and len(low_mono_selected) > 0:
            log_func(f"  → LOW-MONO exceeds 20%: {low_mono_percentage:.1f}%", "WARNING")
        if exceeds_limit:
            log_func(
                f"  → Total slots exceed limit: {total_slots:.2f} > {liczba_n:.2f}",
                "WARNING",
            )
        if outside_n_percentage > 20.0:
            log_func(
                f"  → Outside-N slots exceed 20%: {outside_n_percentage:.1f}%",
                "WARNING",
            )
    else:
        log_func("Phase 1 satisfies constraints - optimizing for potential improvement")

    # Use CP-SAT to globally optimize with ALL publications
    m = cp_model.CpModel()

    # Decision variables for ALL publications (not just phase1 selected!)
    y = {p.id: m.NewBoolVar(f"y_{p.id[0]}_{p.id[1]}") for p in all_pubs}

    # CRITICAL: Add hints from phase 1 for warm-starting
    # This helps the solver converge faster by starting from a good solution
    # NOTE: Must iterate over unique pub IDs (y.keys()), not all_pubs,
    # because all_pubs may contain duplicates (same pub for multiple authors).
    # CP-SAT returns MODEL_INVALID if AddHint is called multiple times
    # for the same variable, even with the same value.
    for pub_id in y.keys():
        was_selected_in_phase1 = pub_id in phase1_selected_ids
        m.AddHint(y[pub_id], was_selected_in_phase1)

    # Objective: maximize points from ALL publications
    m.Maximize(sum(p.points * y[p.id] for p in all_pubs))

    # Per-author constraints (now using all_pubs)
    _add_per_author_constraints(m, y, all_pubs, authors, author_slot_limits)

    # Institution quota constraint: low-point monographies <= 20%
    low_mono_pubs = [p for p in all_pubs if is_low_mono(p)]
    if low_mono_pubs:
        low_mono_count = sum(y[p.id] for p in low_mono_pubs)
        total_count = sum(y[p.id] for p in all_pubs)
        m.Add(5 * low_mono_count <= total_count)  # 20% limit

    # Institution-level total slots constraint
    if liczba_n is not None:
        institution_total_slots = sum(slot_units(p) * y[p.id] for p in all_pubs)
        m.Add(institution_total_slots <= int(liczba_n * SCALE))
        log_func(f"Institution constraint: total slots <= {liczba_n:.2f}")

    # Institution constraint: slots from outside-N authors <= 20%
    pubs_outside_n = [p for p in all_pubs if not p.jest_w_n]
    if pubs_outside_n:
        outside_n_slots_expr = sum(slot_units(p) * y[p.id] for p in pubs_outside_n)
        total_slots_expr = sum(slot_units(p) * y[p.id] for p in all_pubs)
        # outside_n / total <= 0.2  =>  5 * outside_n <= total
        m.Add(5 * outside_n_slots_expr <= total_slots_expr)
        log_func("Institution constraint: outside-N slots <= 20% of total")

    # Solve with configured solver (30 min timeout for institution-level)
    log_func("Starting CP-SAT solver (30 min timeout, progress logging enabled)...")
    solver = configure_solver(
        timeout_seconds=1800.0, log_progress=True, quality_mode="thorough"
    )
    callback = SolutionCallback(y, all_pubs, verbose=True, log_func=log_func)
    status = solver.Solve(m, callback)
    log_func(callback.get_summary())

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        log_func("Could not satisfy institution constraints!", "ERROR")
        raise RuntimeError("Could not satisfy institution constraints!")

    is_optimal = status == cp_model.OPTIMAL
    opt_status = "OPTIMAL" if is_optimal else "FEASIBLE (timeout)"

    # Calculate optimality gap
    gap_percent, best_bound = _calculate_optimality_gap(solver)

    # Extract selected publications
    final_selected = []
    for p in all_pubs:
        if solver.Value(y[p.id]) == 1:
            final_selected.append(p)

    total_points = sum(p.points for p in final_selected)
    final_slots = sum(p.base_slots for p in final_selected)
    phase1_points = sum(p.points for p in phase1_selected)

    # Report improvement (if any)
    point_diff = total_points - phase1_points
    if point_diff > 0.01:
        log_func(f"IMPROVED by {point_diff:.1f} points over phase 1 result!", "SUCCESS")
    elif point_diff < -0.01:
        log_func(
            f"Adjusted by {point_diff:.1f} points (constraints required)", "WARNING"
        )

    log_func(
        f"Final selection: {len(final_selected)} publications, "
        f"{total_points:.1f} points, {final_slots:.2f} slots ({opt_status})"
    )

    if gap_percent is not None:
        log_func(f"Optimality gap: {gap_percent:.2f}%")

    return final_selected, total_points, is_optimal, gap_percent, best_bound


def validate_author_limits(
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
                f"Author {author_id}: {mono_slots:.2f} mono slots > "
                f"{limits['mono']} limit!",
                "ERROR",
            )
            validation_passed = False

    if validation_passed:
        log_func("All slot limits satisfied", "SUCCESS")
    else:
        log_func("Validation failed - slot limits exceeded!", "ERROR")

    return validation_passed


def build_optimization_results(
    dyscyplina_nazwa: str,
    all_selected: list[Pub],
    pubs: list[Pub],
    authors: list[int],
    author_slot_limits: dict,
    total_points: float,
    validation_passed: bool,
    is_optimal: bool = True,
    optimality_gap_percent: float | None = None,
    best_bound: float | None = None,
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
        is_optimal: Whether all solvers found OPTIMAL solutions
        optimality_gap_percent: Optimality gap percentage (None if OPTIMAL)
        best_bound: Theoretical upper bound from solver (None if OPTIMAL)

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
        is_optimal=is_optimal,
        optimality_gap_percent=optimality_gap_percent,
        best_bound=best_bound,
    )


@dataclass
class PinningCandidate:
    """Represents a candidate for pinning (re-pinning an unpinned author)."""

    publication_id: tuple  # (content_type_id, object_id)
    author_id: int
    points: float
    slots: float
    efficiency: float  # points / slots
    author_free_slots: float  # How many slots author has available


def _calculate_author_free_slots(
    all_selected: list[Pub], author_slot_limits: dict
) -> dict[int, float]:
    """Calculate free slots per author based on Phase 2 results."""
    from collections import defaultdict

    author_used_slots: dict[int, float] = defaultdict(float)
    for p in all_selected:
        author_used_slots[p.author] += p.base_slots

    author_free_slots: dict[int, float] = {}
    for author_id, limits in author_slot_limits.items():
        used = author_used_slots.get(author_id, 0.0)
        free = limits["total"] - used
        author_free_slots[author_id] = free

    return author_free_slots


def _get_autor_model_for_content_type(content_type_id: int, ct_ciagle_id: int):
    """Return the appropriate Autor model for the given content type."""
    from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

    if content_type_id == ct_ciagle_id:
        return Wydawnictwo_Ciagle_Autor
    return Wydawnictwo_Zwarte_Autor


def _get_candidate_from_assignment(
    wa, pub_id: tuple, author_free_slots: dict, dyscyplina_id: int
) -> PinningCandidate | None:
    """Create a PinningCandidate from an author assignment if valid."""
    from bpp.models import Cache_Punktacja_Autora_Query

    if not wa.jednostka or not wa.jednostka.skupia_pracownikow:
        return None

    author_id = wa.autor_id
    free_slots = author_free_slots.get(author_id, 0.0)
    if free_slots <= 0:
        return None

    try:
        cache_entry = Cache_Punktacja_Autora_Query.objects.get(
            rekord_id=pub_id,
            autor_id=author_id,
            dyscyplina_id=dyscyplina_id,
        )
        points = float(cache_entry.pkdaut)
        slots = float(cache_entry.slot)
    except Cache_Punktacja_Autora_Query.DoesNotExist:
        return None

    if free_slots < slots:
        return None

    efficiency = points / slots if slots > 0 else 0

    return PinningCandidate(
        publication_id=pub_id,
        author_id=author_id,
        points=points,
        slots=slots,
        efficiency=efficiency,
        author_free_slots=free_slots,
    )


def _log_pinning_candidates(candidates: list[PinningCandidate], log_func) -> None:
    """Log the top pinning candidates."""
    log_func(f"Found {len(candidates)} pinning candidates")

    for i, c in enumerate(candidates[:10], 1):
        log_func(
            f"  {i}. Author {c.author_id}: {c.points:.1f} pts, "
            f"{c.slots:.2f} slots, efficiency={c.efficiency:.2f}, "
            f"free_slots={c.author_free_slots:.2f}"
        )

    if len(candidates) > 10:
        log_func(f"  ... and {len(candidates) - 10} more")


def analyze_pinning_candidates(
    all_selected: list[Pub],
    all_pubs: list[Pub],
    author_slot_limits: dict,
    dyscyplina_id: int,
    log_func,
) -> list[PinningCandidate]:
    """
    Phase 3: Find unpinned authors who can be re-pinned to utilize free slots.

    A candidate is valid when:
    1. Author has FREE slots (limit - used_slots > publication slots)
    2. Publication is NOT selected by any currently pinned author

    Args:
        all_selected: List of all selected publications from Phase 2
        all_pubs: List of all available publications
        author_slot_limits: Dictionary of slot limits per author
        dyscyplina_id: ID of the discipline
        log_func: Function for logging

    Returns:
        List of PinningCandidate objects sorted by efficiency (descending)
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    log_func("=" * 80)
    log_func("PHASE 3 ANALYSIS: Finding pinning candidates")
    log_func("=" * 80)

    author_free_slots = _calculate_author_free_slots(all_selected, author_slot_limits)
    selected_pub_ids = {p.id for p in all_selected}

    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    candidates = []
    unique_pub_ids = {p.id for p in all_pubs}

    for pub_id in unique_pub_ids:
        content_type_id, object_id = pub_id

        if pub_id in selected_pub_ids:
            continue

        if content_type_id not in (ct_ciagle.id, ct_zwarte.id):
            continue

        AutorModel = _get_autor_model_for_content_type(  # noqa: N806
            content_type_id, ct_ciagle.id
        )

        unpinned_authors = AutorModel.objects.filter(
            rekord_id=object_id,
            dyscyplina_naukowa_id=dyscyplina_id,
            przypieta=False,
            afiliuje=True,
        ).select_related("autor", "jednostka")

        for wa in unpinned_authors:
            candidate = _get_candidate_from_assignment(
                wa, pub_id, author_free_slots, dyscyplina_id
            )
            if candidate:
                candidates.append(candidate)

    candidates.sort(key=lambda c: c.efficiency, reverse=True)
    _log_pinning_candidates(candidates, log_func)

    return candidates


def run_single_phase_optimization(  # noqa: C901
    pubs: list[Pub],
    authors: list[int],
    author_slot_limits: dict,
    liczba_n: float | None,
    verbose: bool,
    log_func,
) -> tuple[list[Pub], float, bool, float | None, float | None]:
    """
    Run single-phase optimization using global CP-SAT with all constraints.

    Args:
        pubs: List of all publications
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        liczba_n: Institution-level slot limit (3N - sankcje, used directly)
        verbose: Show detailed progress
        log_func: Function to call for logging

    Returns:
        Tuple of (selected publications, total_points, is_optimal, gap_percent, best_bound)
        is_optimal is True if solver found OPTIMAL solution
        gap_percent and best_bound may be None if not available
    """
    log_func("=" * 80)
    log_func("SINGLE-PHASE: Global CP-SAT optimization with all constraints")
    log_func("=" * 80)

    if not pubs:
        return [], 0.0, True, None, None  # Empty is trivially optimal

    # Create global CP-SAT model
    m = cp_model.CpModel()

    # Decision variables for ALL publications
    x = {p.id: m.NewBoolVar(f"x_{p.id[0]}_{p.id[1]}") for p in pubs}

    # Objective: maximize total points
    m.Maximize(sum(p.points * x[p.id] for p in pubs))

    # Per-author constraints
    log_func(f"Adding per-author constraints for {len(authors)} authors...")
    for author_id in authors:
        author_pubs = [p for p in pubs if p.author == author_id]
        if not author_pubs:
            continue

        limits = author_slot_limits[author_id]

        # Total slots constraint
        m.Add(
            sum(slot_units(p) * x[p.id] for p in author_pubs)
            <= int(limits["total"] * SCALE)
        )

        # Monography slots constraint
        mono_pubs = [p for p in author_pubs if p.kind == "monography"]
        if mono_pubs:
            m.Add(
                sum(slot_units(p) * x[p.id] for p in mono_pubs)
                <= int(limits["mono"] * SCALE)
            )

    # Institution constraint 1: LOW-MONO <= 20% of publications
    log_func("Adding institution constraint: LOW-MONO <= 20%...")
    low_mono_pubs = [p for p in pubs if is_low_mono(p)]
    if low_mono_pubs:
        low_mono_count = sum(x[p.id] for p in low_mono_pubs)
        total_count = sum(x[p.id] for p in pubs)
        m.Add(5 * low_mono_count <= total_count)  # 20% limit

    # Institution constraint 2: Total slots <= limit (3N - sankcje)
    if liczba_n is not None:
        log_func(f"Adding institution constraint: total slots <= {liczba_n:.2f}...")
        institution_total_slots = sum(slot_units(p) * x[p.id] for p in pubs)
        m.Add(institution_total_slots <= int(liczba_n * SCALE))

    # Institution constraint 3: Outside-N slots <= 20% of total slots
    log_func("Adding institution constraint: outside-N slots <= 20%...")
    pubs_outside_n = [p for p in pubs if not p.jest_w_n]
    if pubs_outside_n:
        outside_n_slots_expr = sum(slot_units(p) * x[p.id] for p in pubs_outside_n)
        total_slots_expr = sum(slot_units(p) * x[p.id] for p in pubs)
        # outside_n / total <= 0.2  =>  5 * outside_n <= total
        m.Add(5 * outside_n_slots_expr <= total_slots_expr)

    # Solve with configured solver (30 min timeout for global optimization)
    log_func("Starting CP-SAT solver (30 min timeout, progress logging enabled)...")
    solver = configure_solver(
        timeout_seconds=1800.0, log_progress=True, quality_mode="thorough"
    )
    callback = SolutionCallback(x, pubs, verbose=verbose, log_func=log_func)
    status = solver.Solve(m, callback)
    log_func(callback.get_summary())

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        log_func("Could not find feasible solution!", "ERROR")
        raise RuntimeError("Could not find feasible solution with all constraints!")

    is_optimal = status == cp_model.OPTIMAL

    # Calculate optimality gap
    gap_percent, best_bound = _calculate_optimality_gap(solver)

    # Extract selected publications
    selected = []
    for p in pubs:
        if solver.Value(x[p.id]) == 1:
            selected.append(p)

    total_points = sum(p.points for p in selected)
    total_slots = sum(p.base_slots for p in selected)
    low_mono_count = len([p for p in selected if is_low_mono(p)])
    low_mono_pct = (100.0 * low_mono_count / len(selected)) if selected else 0.0
    outside_n_slots_val = sum(p.base_slots for p in selected if not p.jest_w_n)
    outside_n_pct = (
        (100.0 * outside_n_slots_val / total_slots) if total_slots > 0 else 0.0
    )

    opt_status = "OPTIMAL" if is_optimal else "FEASIBLE (timeout)"
    log_func(
        f"Solution found: {len(selected)} publications, "
        f"{total_points:.1f} points, {total_slots:.2f} slots ({opt_status})"
    )
    log_func(f"  LOW-MONO: {low_mono_count}/{len(selected)} ({low_mono_pct:.1f}%)")
    if liczba_n is not None:
        log_func(f"  Total slots: {total_slots:.2f} / {liczba_n:.2f} (limit)")
    log_func(
        f"  Outside-N: {outside_n_slots_val:.2f}/{total_slots:.2f} "
        f"({outside_n_pct:.1f}%)"
    )
    if gap_percent is not None:
        log_func(f"  Optimality gap: {gap_percent:.2f}%")

    return selected, total_points, is_optimal, gap_percent, best_bound
