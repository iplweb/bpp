"""
Optimization phase functions for evaluation optimization.

This module contains the phase 1 (per-author) and phase 2 (institution-level)
optimization functions, as well as validation and result building functions.
"""

from ortools.sat.python import cp_model

from .data_structures import SCALE, OptimizationResults, Pub, is_low_mono, slot_units
from .solver import SolutionCallback, solve_author_knapsack


def run_phase1_per_author_optimization(
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
                f"  Selected: {len(selected)} pubs, "
                f"{author_points:.1f} points, {author_slots:.2f} slots"
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


def apply_institution_constraints(  # noqa: C901
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
        f"Low-point monographies: {len(low_mono_selected)}/{len(all_selected)} "
        f"({low_mono_percentage:.1f}%)"
    )

    # Calculate total slots for Phase 1 result
    total_slots = sum(p.base_slots for p in all_selected)

    # Calculate outside-N slots percentage
    outside_n_slots = sum(p.base_slots for p in all_selected if not p.jest_w_n)
    outside_n_percentage = (
        (100.0 * outside_n_slots / total_slots) if total_slots > 0 else 0
    )

    log_func(
        f"Outside-N slots: {outside_n_slots:.2f}/{total_slots:.2f} "
        f"({outside_n_percentage:.1f}%)"
    )

    # Check if 3×N constraint is violated
    exceeds_3n = False
    if liczba_n is not None:
        max_slots = 3 * liczba_n
        log_func(f"Total slots vs 3×N limit: {total_slots:.2f} / {max_slots:.2f}")
        if total_slots > max_slots:
            exceeds_3n = True
            log_func(
                f"Exceeds 3×N limit by {total_slots - max_slots:.2f} slots", "WARNING"
            )

    # Check if any institution constraint is violated
    needs_adjustment = (
        (low_mono_percentage > 20.0 and len(low_mono_selected) > 0)
        or exceeds_3n
        or outside_n_percentage > 20.0
    )

    # If any institution constraint is violated, we need to adjust
    if needs_adjustment:
        log_func("Institution constraints violated - adjusting selection...", "WARNING")
        if low_mono_percentage > 20.0 and len(low_mono_selected) > 0:
            log_func(f"  → LOW-MONO exceeds 20%: {low_mono_percentage:.1f}%", "WARNING")
        if exceeds_3n:
            log_func(
                f"  → Total slots exceed 3×N: {total_slots:.2f} > {3 * liczba_n:.2f}",
                "WARNING",
            )
        if outside_n_percentage > 20.0:
            log_func(
                f"  → Outside-N slots exceed 20%: {outside_n_percentage:.1f}%",
                "WARNING",
            )

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
            m.Add(institution_total_slots <= int(3 * liczba_n * SCALE))
            log_func(
                f"Institution constraint: total slots <= {3 * liczba_n:.2f} "
                f"(3×N where N={liczba_n:.2f})"
            )

        # Institution constraint: slots from outside-N authors <= 20%
        pubs_outside_n = [p for p in all_selected if not p.jest_w_n]
        if pubs_outside_n:
            outside_n_slots_expr = sum(slot_units(p) * y[p.id] for p in pubs_outside_n)
            total_slots_expr = sum(slot_units(p) * y[p.id] for p in all_selected)
            # outside_n / total <= 0.2  =>  5 * outside_n <= total
            m.Add(5 * outside_n_slots_expr <= total_slots_expr)
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
            f"Adjusted selection: {len(all_selected)} publications, "
            f"{total_points:.1f} points"
        )
    else:
        total_points = sum(p.points for p in all_selected)
        log_func("Institution constraints satisfied", "SUCCESS")

    return all_selected, total_points


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


def run_single_phase_optimization(  # noqa: C901
    pubs: list[Pub],
    authors: list[int],
    author_slot_limits: dict,
    liczba_n: float | None,
    verbose: bool,
    log_func,
) -> tuple[list[Pub], float]:
    """
    Run single-phase optimization using global CP-SAT with all constraints.

    Args:
        pubs: List of all publications
        authors: List of author IDs
        author_slot_limits: Dictionary of slot limits per author
        liczba_n: Institution-level slot limit
        verbose: Show detailed progress
        log_func: Function to call for logging

    Returns:
        Tuple of (selected publications, total_points)
    """
    log_func("=" * 80)
    log_func("SINGLE-PHASE: Global CP-SAT optimization with all constraints")
    log_func("=" * 80)

    if not pubs:
        return [], 0.0

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

    # Institution constraint 2: Total slots <= 3×N
    if liczba_n is not None:
        log_func(
            f"Adding institution constraint: total slots <= 3×N (3×{liczba_n:.2f})..."
        )
        institution_total_slots = sum(slot_units(p) * x[p.id] for p in pubs)
        m.Add(institution_total_slots <= int(3 * liczba_n * SCALE))

    # Institution constraint 3: Outside-N slots <= 20% of total slots
    log_func("Adding institution constraint: outside-N slots <= 20%...")
    pubs_outside_n = [p for p in pubs if not p.jest_w_n]
    if pubs_outside_n:
        outside_n_slots_expr = sum(slot_units(p) * x[p.id] for p in pubs_outside_n)
        total_slots_expr = sum(slot_units(p) * x[p.id] for p in pubs)
        # outside_n / total <= 0.2  =>  5 * outside_n <= total
        m.Add(5 * outside_n_slots_expr <= total_slots_expr)

    # Solve with progress callback
    log_func("Solving global CP-SAT problem...")
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = (
        8  # Use multiple threads for better performance
    )

    if verbose:
        callback = SolutionCallback(x, pubs, verbose=True)
        status = solver.Solve(m, callback)
        print()  # New line after progress dots
    else:
        status = solver.Solve(m)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        log_func("Could not find feasible solution!", "ERROR")
        raise RuntimeError("Could not find feasible solution with all constraints!")

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

    log_func(
        f"Solution found: {len(selected)} publications, "
        f"{total_points:.1f} points, {total_slots:.2f} slots"
    )
    log_func(f"  LOW-MONO: {low_mono_count}/{len(selected)} ({low_mono_pct:.1f}%)")
    if liczba_n is not None:
        log_func(f"  Total slots: {total_slots:.2f} / {3 * liczba_n:.2f} (3×N)")
    log_func(
        f"  Outside-N: {outside_n_slots_val:.2f}/{total_slots:.2f} "
        f"({outside_n_pct:.1f}%)"
    )

    return selected, total_points
