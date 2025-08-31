import logging

from celery import shared_task
from celery.result import AsyncResult
from django.core.cache import cache

from komparator_pbn_udzialy.utils import KomparatorDyscyplinPBN

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def porownaj_dyscypliny_pbn_task(self, clear_existing=False):
    """
    Celery task do porównywania dyscyplin w tle.
    Śledzi postęp i zapisuje go w cache.
    """
    task_id = self.request.id
    cache_key = f"komparator_pbn_progress_{task_id}"

    try:
        # Zapisz początkowy status
        cache.set(
            cache_key,
            {
                "status": "PROGRESS",
                "current": 0,
                "total": 0,
                "message": "Inicjalizacja...",
                "stats": {},
            },
            3600,
        )  # Cache na 1 godzinę

        # Uruchom komparator
        komparator = KomparatorDyscyplinPBN(
            clear_existing=clear_existing, show_progress=False  # Nie pokazuj tqdm w tle
        )

        # Monkeypatching process_oswiadczenie aby raportować postęp
        original_process = komparator.process_oswiadczenie

        def process_with_progress(oswiadczenie):
            result = original_process(oswiadczenie)

            # Aktualizuj postęp co 10 rekordów
            if komparator.stats["processed"] % 10 == 0:
                cache.set(
                    cache_key,
                    {
                        "status": "PROGRESS",
                        "current": komparator.stats["processed"],
                        "total": getattr(komparator, "_total", 0),
                        "message": f"Przetwarzanie oświadczeń... ({komparator.stats['processed']}"
                        f" / {getattr(komparator, '_total', 0)})",
                        "stats": komparator.stats,
                    },
                    3600,
                )

                # Aktualizuj meta Celery
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": komparator.stats["processed"],
                        "total": getattr(komparator, "_total", 0),
                        "stats": komparator.stats,
                    },
                )

            return result

        komparator.process_oswiadczenie = process_with_progress

        # Zapisz łączną liczbę rekordów
        from pbn_api.models import OswiadczenieInstytucji

        total = OswiadczenieInstytucji.objects.count()
        komparator._total = total

        # Uruchom porównanie
        stats = komparator.run()

        # Zapisz końcowy wynik
        cache.set(
            cache_key,
            {
                "status": "SUCCESS",
                "current": stats["processed"],
                "total": stats["processed"],
                "message": "Porównywanie zakończone pomyślnie",
                "stats": stats,
            },
            3600,
        )

        return {
            "status": "SUCCESS",
            "stats": stats,
            "message": f"Zakończono porównywanie. Przetworzono: {stats['processed']}, "
            f"znaleziono rozbieżności: {stats['discrepancies_found']}",
        }

    except Exception as e:
        logger.exception("Błąd podczas porównywania dyscyplin")

        # Zapisz błąd w cache
        cache.set(
            cache_key,
            {
                "status": "FAILURE",
                "message": f"Błąd: {str(e)}",
                "stats": getattr(komparator, "stats", {}),
            },
            3600,
        )

        raise


def get_task_status(task_id):
    """
    Pobiera status zadania z cache lub Celery.
    """
    # Najpierw sprawdź cache
    cache_key = f"komparator_pbn_progress_{task_id}"
    cached_status = cache.get(cache_key)

    if cached_status:
        return cached_status

    # Jeśli nie ma w cache, sprawdź Celery
    result = AsyncResult(task_id)

    if result.state == "PENDING":
        return {
            "status": "PENDING",
            "message": "Zadanie oczekuje w kolejce...",
            "current": 0,
            "total": 0,
        }
    elif result.state == "PROGRESS":
        return {
            "status": "PROGRESS",
            "current": result.info.get("current", 0),
            "total": result.info.get("total", 0),
            "message": "Przetwarzanie...",
            "stats": result.info.get("stats", {}),
        }
    elif result.state == "SUCCESS":
        return {
            "status": "SUCCESS",
            "message": result.info.get("message", "Zakończono"),
            "stats": result.info.get("stats", {}),
        }
    else:  # FAILURE
        return {
            "status": "FAILURE",
            "message": str(result.info) if result.info else "Nieznany błąd",
        }
