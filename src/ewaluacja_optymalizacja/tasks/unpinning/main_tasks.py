"""Główne taski Celery dla analizy unpinning - punkty wejścia."""

import logging

from celery import shared_task
from celery_singleton import Singleton

from .analysis import _analyze_multi_author_works_impl

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def run_unpinning_after_metrics_wrapper(
    self, metrics_result, uczelnia_id, dyscyplina_id=None, min_slot_filled=0.8
):
    """
    Wrapper wywołujący analizę unpinning po zakończeniu metryk.
    Używany w Celery chain: metryki -> unpinning.

    Args:
        metrics_result: Wynik zadania generuj_metryki_task_parallel (ignorowany)
        uczelnia_id: ID uczelni
        dyscyplina_id: ID dyscypliny (opcjonalnie, jeśli None to wszystkie)
        min_slot_filled: Minimalny próg wypełnienia slotów (domyślnie 0.8 = 80%)

    Returns:
        Dictionary z wynikami analizy unpinning
    """
    from ewaluacja_metryki.models import MetrykaAutora

    logger.info(
        f"Metrics task completed with result: {metrics_result}. "
        f"Starting unpinning analysis for uczelnia_id={uczelnia_id}, "
        f"dyscyplina_id={dyscyplina_id}"
    )

    # Sprawdź ile metryk zostało utworzonych
    metrics_count = MetrykaAutora.objects.count()
    logger.info(f"Found {metrics_count} metrics in database")

    if metrics_count == 0:
        logger.warning(
            "No metrics found in database! Unpinning analysis will likely find nothing."
        )

    # Aktualizuj status - faza unpinning rozpoczęta (50% całości)
    self.update_state(
        state="PROGRESS",
        meta={
            "stage": "unpinning",
            "step": "starting",
            "progress": 50,
            "metrics_count": metrics_count,
            "metrics_result": metrics_result,
        },
    )

    # Wywołaj analizę unpinning z offsetem 50 (metryki zajęły 0-50%)
    result = _analyze_multi_author_works_impl(
        self, uczelnia_id, dyscyplina_id, min_slot_filled, progress_offset=50
    )

    # Dodaj informacje o metrykach do wyniku
    result["metrics_count"] = metrics_count
    result["metrics_result"] = metrics_result

    logger.info(f"Unpinning analysis completed: {result}")

    return result


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id", "dyscyplina_id"],
    lock_expiry=3600,
    bind=True,
    time_limit=1800,
)
def analyze_multi_author_works_task(
    self,
    uczelnia_id,
    dyscyplina_id=None,
    min_slot_filled=0.8,
    parallel=True,
    num_workers=4,
):
    """
    Analizuje prace wieloautorskie szukając możliwości odpinania.

    Znajdź prace gdzie:
    - Autor A: praca NIE weszła do zebranych (nie ma w prace_nazbierane)
              AND ma PEŁNE sloty (slot_nazbierany >= min_slot_filled * slot_maksymalny)
    - Autor B: praca WESZŁA do zebranych (jest w prace_nazbierane)
              AND ma niepełne sloty (może wziąć więcej)
    - Odpięcie dla Autora A umożliwi Autorowi B większy udział

    Args:
        uczelnia_id: ID uczelni
        dyscyplina_id: ID dyscypliny (opcjonalnie, jeśli None to wszystkie)
        min_slot_filled: Minimalny próg wypełnienia slotów (domyślnie 0.8 = 80%)
        parallel: Czy używać równoległego przetwarzania (domyślnie True)
        num_workers: Liczba workerów (domyślnie 4)

    Returns:
        Dictionary z wynikami analizy
    """
    return _analyze_multi_author_works_impl(
        self,
        uczelnia_id,
        dyscyplina_id,
        min_slot_filled,
        progress_offset=0,
        parallel=parallel,
        num_workers=num_workers,
    )
