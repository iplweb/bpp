"""
Solver functions for evaluation optimization.

This module contains the knapsack solver and callback for the CP-SAT solver.
"""

import os
import sys

from ortools.sat.python import cp_model

from .data_structures import SCALE, Pub


def configure_solver(timeout_seconds: float | None = 600.0) -> cp_model.CpSolver:
    """
    Configure CP-SAT solver with optimal settings.

    Args:
        timeout_seconds: Maximum solving time in seconds. None means no limit.

    Returns:
        Configured CpSolver instance
    """
    solver = cp_model.CpSolver()

    # Use all available CPUs for better performance
    solver.parameters.num_search_workers = os.cpu_count() or 8

    # Ensure deterministic results despite parallelization
    solver.parameters.random_seed = 42
    solver.parameters.interleave_search = True

    # Set timeout to prevent indefinite execution (if specified)
    if timeout_seconds is not None:
        solver.parameters.max_time_in_seconds = timeout_seconds

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
