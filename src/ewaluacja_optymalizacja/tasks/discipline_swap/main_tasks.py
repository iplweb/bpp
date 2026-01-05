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
    rok_min=2022,
    rok_max=2025,
):
    """
    Analizuje publikacje pod kątem możliwości zamiany dyscyplin.

    Znajduje publikacje gdzie:
    - Autor ma przypisane dwie dyscypliny (dyscyplina + subdyscyplina)
    - Zamiana dyscypliny z głównej na subdyscyplinę (lub odwrotnie)
      zwiększa całkowitą punktację publikacji

    Args:
        uczelnia_id: ID uczelni
        rok_min: Minimalny rok analizy (domyślnie 2022)
        rok_max: Maksymalny rok analizy (domyślnie 2025)

    Returns:
        Dictionary z wynikami analizy
    """
    from ...models import StatusDisciplineSwapAnalysis

    logger.info(
        f"Starting discipline swap analysis for uczelnia_id={uczelnia_id}, "
        f"years {rok_min}-{rok_max}"
    )

    # Oznacz status jako w trakcie
    status = StatusDisciplineSwapAnalysis.get_or_create()
    status.rozpocznij(task_id=str(self.request.id))

    try:
        result = _analyze_discipline_swap_impl(
            self,
            uczelnia_id,
            rok_min=rok_min,
            rok_max=rok_max,
        )
        return result

    except Exception as e:
        logger.error(f"Discipline swap analysis failed: {e}", exc_info=True)
        status.zakoncz(f"Błąd: {str(e)[:200]}")
        raise
