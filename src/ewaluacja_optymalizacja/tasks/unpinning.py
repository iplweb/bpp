"""
Taski analizy unpinning - warstwa kompatybilności wstecznej.

Ten moduł zachowuje kompatybilność wsteczną. Rzeczywista implementacja
została przeniesiona do podmodułu `unpinning/`:

- unpinning/clustering.py - funkcje klasteryzacji i partycjonowania prac
- unpinning/simulation.py - symulacja odpięcia i obliczanie korzyści
- unpinning/analysis.py - główna implementacja analizy
- unpinning/workers.py - Celery worker taski do równoległego przetwarzania
- unpinning/main_tasks.py - główne taski Celery (punkty wejścia)

Wszystkie eksporty są dostępne zarówno przez ten moduł jak i przez
`ewaluacja_optymalizacja.tasks.unpinning.*` dla zachowania kompatybilności.
"""

# Re-export all public symbols from the new submodule
from .unpinning import (
    # Main analysis implementation
    _analyze_multi_author_works_impl,
    # Main entry point tasks
    analyze_multi_author_works_task,
    # Worker tasks
    analyze_unpinning_worker_task,
    # Clustering utilities
    build_author_clusters,
    collect_unpinning_results,
    partition_works_into_chunks,
    run_unpinning_after_metrics_wrapper,
    # Simulation
    simulate_unpinning_benefit,
)

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
