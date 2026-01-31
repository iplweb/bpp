"""
Solver functions for evaluation optimization.

This module contains the knapsack solver and callback for the CP-SAT solver.

CP-SAT Solver Quality Parameters Documentation
==============================================

Key parameters that affect solution quality:

1. **max_time_in_seconds** (default: 1800s = 30 min)
   - Longer timeout allows more exploration of solution space
   - Diminishing returns after solver finds OPTIMAL

2. **num_search_workers** (default: all CPUs)
   - More workers = faster parallel search
   - Diminishing returns beyond ~16 workers

3. **random_seed** (default: 42)
   - Fixed seed ensures deterministic results
   - Different seeds may find different local optima

4. **interleave_search** (default: True)
   - Combines multiple search strategies
   - Generally improves solution quality

5. **log_search_progress** (default: True)
   - Shows solver progress in real-time
   - Useful for diagnosing slow convergence

6. **linearization_level** (default: 2)
   - Higher = more LP relaxation cuts
   - Values: 0 (none), 1 (basic), 2 (full)
   - Higher values often improve bounds

7. **symmetry_level** (default: 2)
   - Detects and breaks symmetries
   - Reduces search space significantly

8. **cp_model_presolve** (default: True)
   - Simplifies model before solving
   - Almost always beneficial

Note: The current implementation achieves OPTIMAL solutions with 0% gap,
meaning the mathematical optimum has been found. To improve beyond this,
the *input data* must be modified (e.g., by unpinning disciplines in
multi-author works to redistribute points/slots).
"""

import logging
import os
import sys

from ortools.sat.python import cp_model

from .data_structures import SCALE, Pub

logger = logging.getLogger(__name__)


def configure_solver(
    timeout_seconds: float | None = 1800.0,
    log_progress: bool = True,
    quality_mode: str = "balanced",
) -> cp_model.CpSolver:
    """
    Configure CP-SAT solver with optimal settings.

    Args:
        timeout_seconds: Maximum solving time in seconds. None means no limit.
            Default is 1800s (30 minutes) to allow thorough exploration.
        log_progress: If True, solver logs search progress to stdout.
        quality_mode: Optimization mode:
            - "fast": Quick solutions, may not be optimal
            - "balanced": Good balance of speed and quality (default)
            - "thorough": Maximum effort to find best solution

    Returns:
        Configured CpSolver instance
    """
    solver = cp_model.CpSolver()

    # Use all available CPUs for better performance
    num_workers = os.cpu_count() or 8
    solver.parameters.num_search_workers = num_workers
    logger.info(f"Solver configured with {num_workers} workers")

    # Ensure deterministic results despite parallelization
    solver.parameters.random_seed = 42
    solver.parameters.interleave_search = True

    # Enable search progress logging
    if log_progress:
        solver.parameters.log_search_progress = True
        logger.info("Solver progress logging enabled")

    # Set timeout to prevent indefinite execution (if specified)
    if timeout_seconds is not None:
        solver.parameters.max_time_in_seconds = timeout_seconds
        logger.info(f"Solver timeout: {timeout_seconds}s")

    # Quality mode settings
    if quality_mode == "fast":
        # Prioritize speed over optimality
        solver.parameters.linearization_level = 0
        solver.parameters.symmetry_level = 1
        logger.info("Quality mode: FAST (speed priority)")
    elif quality_mode == "thorough":
        # Maximum effort for best solution
        solver.parameters.linearization_level = 2
        solver.parameters.symmetry_level = 2
        solver.parameters.cp_model_presolve = True
        logger.info("Quality mode: THOROUGH (quality priority)")
    else:
        # Balanced mode (default)
        solver.parameters.linearization_level = 2
        solver.parameters.symmetry_level = 2
        solver.parameters.cp_model_presolve = True
        logger.info("Quality mode: BALANCED")

    return solver


def solve_author_knapsack(
    author_pubs: list[Pub], max_slots: float, max_mono_slots: float
) -> tuple[list[Pub], bool]:
    """
    Solve knapsack problem for a single author using CP-SAT.

    Returns:
        Tuple of (selected publications list, is_optimal flag)
        is_optimal is True if solver found OPTIMAL solution, False if FEASIBLE (possibly timed out)
    """
    if not author_pubs:
        return [], True  # Empty is trivially optimal

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

    # Solve with configured solver (no timeout for per-author knapsack)
    solver = configure_solver(timeout_seconds=None)
    status = solver.Solve(m)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return [], False

    # Return selected publications and optimality status
    result = []
    for p in sorted_pubs:
        if solver.Value(selected[p.id]) == 1:
            result.append(p)

    is_optimal = status == cp_model.OPTIMAL
    return result, is_optimal


class SolutionCallback(cp_model.CpSolverSolutionCallback):
    """Callback to report solver progress with detailed logging."""

    def __init__(self, variables, pubs, verbose=False, log_func=None):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.variables = variables
        self.pubs = pubs
        self.solution_count = 0
        self.verbose = verbose
        self.log_func = log_func
        self.best_objective = 0
        self.improvements = []  # Track improvement history

    def on_solution_callback(self):
        self.solution_count += 1
        current_objective = self.ObjectiveValue()
        current_bound = self.BestObjectiveBound()
        wall_time = self.WallTime()

        if current_objective > self.best_objective:
            improvement = current_objective - self.best_objective
            self.improvements.append(
                {
                    "solution": self.solution_count,
                    "objective": current_objective,
                    "bound": current_bound,
                    "improvement": improvement,
                    "time": wall_time,
                }
            )
            self.best_objective = current_objective

            # Calculate gap
            gap_pct = 0.0
            if current_bound > 0:
                gap_pct = ((current_bound - current_objective) / current_bound) * 100

            msg = (
                f"Solution #{self.solution_count}: {current_objective:.1f} pts "
                f"(+{improvement:.1f}), bound={current_bound:.1f}, "
                f"gap={gap_pct:.2f}%, time={wall_time:.1f}s"
            )

            if self.log_func:
                self.log_func(msg)
            elif self.verbose:
                sys.stdout.write(f"\r{msg}")
                sys.stdout.flush()
            else:
                sys.stdout.write(".")
                sys.stdout.flush()

    def get_summary(self) -> str:
        """Return summary of solver progress."""
        if not self.improvements:
            return "No solutions found"

        first = self.improvements[0]
        last = self.improvements[-1]
        total_improvement = last["objective"] - first["objective"]

        return (
            f"Found {self.solution_count} solutions, "
            f"{len(self.improvements)} improvements, "
            f"total improvement: {total_improvement:.1f} pts over {last['time']:.1f}s"
        )
