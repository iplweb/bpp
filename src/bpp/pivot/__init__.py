"""Tabele krzyżowe (pivot) — generyczny silnik + rejestry per model."""

from .core import (  # noqa: F401
    BRAK,
    PIVOT_MAX_CELLS,
    PIVOT_MAX_PAIRS,
    PivotDimension,
    PivotMetric,
    PivotResult,
    PivotTooLargeError,
    zbuduj_pivot,
)
