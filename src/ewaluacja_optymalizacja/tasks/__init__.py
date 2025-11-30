"""Taski Celery dla modułu ewaluacja_optymalizacja.

Ten moduł eksportuje wszystkie taski dla Celery autodiscover.
"""

from .optimization import (
    optimize_and_unpin_task,
    solve_all_reported_disciplines,
    solve_single_discipline_task,
)
from .reset_pins import reset_all_pins_task
from .unpin_all_sensible import unpin_all_sensible_task
from .unpinning import (
    analyze_multi_author_works_task,
    analyze_unpinning_worker_task,
    collect_unpinning_results,
    run_unpinning_after_metrics_wrapper,
)

__all__ = [
    # optimization.py
    "solve_single_discipline_task",
    "solve_all_reported_disciplines",
    "optimize_and_unpin_task",
    # reset_pins.py
    "reset_all_pins_task",
    # unpinning.py
    "analyze_multi_author_works_task",
    "analyze_unpinning_worker_task",
    "collect_unpinning_results",
    "run_unpinning_after_metrics_wrapper",
    # unpin_all_sensible.py
    "unpin_all_sensible_task",
]
