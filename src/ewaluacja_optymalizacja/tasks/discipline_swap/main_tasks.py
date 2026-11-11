"""Główne taski Celery dla analizy zamiany dyscyplin - punkty wejścia."""

import logging

from celery import shared_task
from celery_singleton import Singleton

from .analysis import _analyze_discipline_swap_impl

logger = logging.getLogger(__name__)


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id"],
    lock_expiry=3600,
    bind=True,
    time_limit=1800,
)
def analyze_discipline_swap_task(
    self,
    uczelnia_id,
    okres_pk=None,
):
    """
    Analizuje publikacje pod kątem możliwości zamiany dyscyplin.

    Znajduje publikacje gdzie:
    - Autor ma przypisane dwie dyscypliny (dyscyplina + subdyscyplina)
    - Zamiana dyscypliny z głównej na subdyscyplinę (lub odwrotnie)
      zwiększa całkowitą punktację publikacji

    Args:
        uczelnia_id: ID uczelni
        okres_pk: PK okresu ewaluacji (``None`` = okres domyślny); analizowane
            są publikacje z lat tego okresu

    Returns:
        Dictionary z wynikami analizy
    """
    from ...models import StatusDisciplineSwapAnalysis
    from ...okres import pobierz_okres

    okres = pobierz_okres(okres_pk)
    logger.info(
        f"Starting discipline swap analysis for uczelnia_id={uczelnia_id}, "
        f"okres {okres}"
    )

    # Oznacz status jako w trakcie
    status = StatusDisciplineSwapAnalysis.get_or_create()
    status.rozpocznij(task_id=str(self.request.id), okres=okres)

    try:
        result = _analyze_discipline_swap_impl(
            self,
            uczelnia_id,
            okres=okres,
        )
        return result

    except Exception as e:
        logger.error(f"Discipline swap analysis failed: {e}", exc_info=True)
        status.zakoncz(f"Błąd: {str(e)[:200]}")
        raise
