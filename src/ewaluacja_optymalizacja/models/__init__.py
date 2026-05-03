"""Modele aplikacji ewaluacja_optymalizacja.

Pakiet podzielony na moduły wg odpowiedzialności:

- :mod:`runs` -- ``OptimizationRun``, ``OptimizationAuthorResult``,
  ``OptimizationPublication`` (przebiegi optymalizacji i ich wyniki).
- :mod:`unpinning` -- ``UnpinningOpportunity`` (analiza możliwości
  odpinania publikacji).
- :mod:`discipline_swap` -- ``DisciplineSwapOpportunity`` (analiza
  możliwości zamiany dyscyplin).
- :mod:`status` -- singletony śledzące status zadań Celery
  (``StatusOptymalizacjiZOdpinaniem``, ``StatusOptymalizacjiBulk``,
  ``StatusUnpinningAnalyzy``, ``StatusDisciplineSwapAnalysis``,
  ``StatusPrzegladarkaRecalc``).

Wszystkie modele są reeksportowane z tego ``__init__.py``, więc importy
``from ewaluacja_optymalizacja.models import <Model>`` działają jak
przed podziałem.
"""

from .discipline_swap import DisciplineSwapOpportunity
from .runs import (
    OptimizationAuthorResult,
    OptimizationPublication,
    OptimizationRun,
)
from .status import (
    StatusDisciplineSwapAnalysis,
    StatusOptymalizacjiBulk,
    StatusOptymalizacjiZOdpinaniem,
    StatusPrzegladarkaRecalc,
    StatusUnpinningAnalyzy,
)
from .unpinning import UnpinningOpportunity

__all__ = [
    "DisciplineSwapOpportunity",
    "OptimizationAuthorResult",
    "OptimizationPublication",
    "OptimizationRun",
    "StatusDisciplineSwapAnalysis",
    "StatusOptymalizacjiBulk",
    "StatusOptymalizacjiZOdpinaniem",
    "StatusPrzegladarkaRecalc",
    "StatusUnpinningAnalyzy",
    "UnpinningOpportunity",
]
