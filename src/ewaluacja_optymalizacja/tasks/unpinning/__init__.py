"""
Moduł analizy unpinning - wykrywanie możliwości odpięcia prac wieloautorskich.

Ten moduł zawiera:
- clustering.py - funkcje klasteryzacji i partycjonowania prac
- simulation.py - symulacja odpięcia i obliczanie korzyści
- analysis.py - główna implementacja analizy
- workers.py - Celery worker taski do równoległego przetwarzania
- main_tasks.py - główne taski Celery (punkty wejścia)

Eksportuje wszystkie publiczne symbole dla zachowania kompatybilności wstecznej.
"""

# Clustering utilities
# Main analysis implementation
from .analysis import _analyze_multi_author_works_impl
from .clustering import build_author_clusters, partition_works_into_chunks

# Main entry point tasks
from .main_tasks import (
    analyze_multi_author_works_task,
    run_unpinning_after_metrics_wrapper,
)

# Simulation
from .simulation import simulate_unpinning_benefit

# Worker tasks
from .workers import analyze_unpinning_worker_task, collect_unpinning_results

__all__ = [
    # Clustering
    "build_author_clusters",
    "partition_works_into_chunks",
    # Simulation
    "simulate_unpinning_benefit",
    # Analysis
    "_analyze_multi_author_works_impl",
    # Worker tasks
    "analyze_unpinning_worker_task",
    "collect_unpinning_results",
    # Main tasks
    "analyze_multi_author_works_task",
    "run_unpinning_after_metrics_wrapper",
]
