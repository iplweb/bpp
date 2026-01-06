"""Pakiet zadań analizy zamiany dyscyplin."""

from .main_tasks import analyze_discipline_swap_task
from .workers import (
    analyze_discipline_swap_worker_task,
    collect_discipline_swap_results,
)

__all__ = [
    "analyze_discipline_swap_task",
    "analyze_discipline_swap_worker_task",
    "collect_discipline_swap_results",
]
