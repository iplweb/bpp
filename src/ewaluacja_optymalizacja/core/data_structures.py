"""
Data structures for evaluation optimization.

This module contains dataclasses and helper functions for representing
publication and optimization result data.
"""

from dataclasses import dataclass

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
    is_optimal: bool = True  # True if all solvers found OPTIMAL solutions
    # Optimality gap information (None if not available or OPTIMAL)
    optimality_gap_percent: float | None = (
        None  # (best_bound - value) / best_bound * 100
    )
    best_bound: float | None = None  # Theoretical upper bound from solver


def slot_units(p: Pub) -> int:
    """Convert float slots to scaled integer units for CP-SAT solver"""
    # Use round() for better precision with 2-decimal slot values
    return round(p.base_slots * SCALE)


def is_low_mono(p: Pub) -> bool:
    """Check if publication is a low-point monography (< 200 points)"""
    return p.kind == "monography" and p.points < 200
