"""
Moduł analizy unpinning - wykrywanie możliwości odpięcia prac wieloautorskich.

Ten moduł zawiera:
- clustering.py - funkcje klasteryzacji i partycjonowania prac
- simulation.py - symulacja odpięcia i obliczanie korzyści
- analysis.py - główna implementacja analizy
- workers.py - Celery worker taski do równoległego przetwarzania
- main_tasks.py - główne taski Celery (punkty wejścia)
- capacity_analysis.py - algorytm capacity-based unpinning (84% dokładności)

Eksportuje wszystkie publiczne symbole dla zachowania kompatybilności wstecznej.
"""

# Main analysis implementation
from .analysis import _analyze_multi_author_works_impl

# Capacity-based unpinning (new algorithm)
from .capacity_analysis import (
    UnpinningCandidate,
    apply_unpinning,
    calculate_author_capacity,
    calculate_author_slot_usage,
    format_unpinning_preview,
    identify_unpinning_candidates,
)

# Clustering utilities
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
    # Capacity-based unpinning
    "UnpinningCandidate",
    "calculate_author_slot_usage",
    "calculate_author_capacity",
    "identify_unpinning_candidates",
    "apply_unpinning",
    "format_unpinning_preview",
    # Worker tasks
    "analyze_unpinning_worker_task",
    "collect_unpinning_results",
    # Main tasks
    "analyze_multi_author_works_task",
    "run_unpinning_after_metrics_wrapper",
]
