"""Zadanie Celery komparatora publikacji PBN (wzorem komparatora źródeł)."""

import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

KLUCZ_POSTEPU = "komparator_publikacji_progress_{task_id}"


@shared_task(bind=True)
def porownaj_publikacje_task(self):
    """Porównuje wszystkie prace powiązane z PBN z lokalną kopią danych PBN.

    Postęp raportuje przez cache i ``update_state`` Celery (jak
    ``pbn_komparator_zrodel.tasks.porownaj_zrodla_task``) oraz — w
    ``core.przelicz`` — w wierszu stanu komparatora (znak życia).
    """
    from .core import PrzeliczanieJuzTrwa, PrzeliczaniePrzejete, przelicz

    cache_key = KLUCZ_POSTEPU.format(task_id=self.request.id)

    def progress_callback(current, total, z_roznicami):
        info = {
            "current": current,
            "total": total,
            "progress": int((current / total) * 100) if total > 0 else 0,
            "stats": {"processed": current, "with_differences": z_roznicami},
        }
        cache.set(cache_key, {"status": "PROGRESS", **info}, 3600)
        self.update_state(state="PROGRESS", meta=info)

    try:
        stats = przelicz(progress_callback=progress_callback)
    except (PrzeliczanieJuzTrwa, PrzeliczaniePrzejete) as e:
        # Komparator liczy inny przebieg — to zadanie nie ma nic do zrobienia
        # i nie rusza ani wyników, ani stanu.
        logger.warning("Komparator publikacji PBN: zadanie pominięte (%r)", e)
        return {"status": "SKIPPED", "message": "Trwa inne przeliczenie"}
    except Exception as e:
        # Stan „błąd” zapisał już ``przelicz`` (``core.oznacz_blad``).
        logger.exception("Błąd podczas porównywania publikacji z PBN")
        cache.set(cache_key, {"status": "FAILURE", "message": str(e)}, 3600)
        raise

    cache.set(cache_key, {"status": "SUCCESS", "stats": stats}, 3600)
    return {
        "status": "SUCCESS",
        "stats": stats,
        "message": f"Porównano {stats['processed']} prac",
    }
