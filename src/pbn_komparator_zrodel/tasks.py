import logging
import sys

import rollbar
from celery import shared_task
from celery.result import AsyncResult
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def porownaj_zrodla_task(self, min_rok=2022, clear_existing=False):
    """
    Celery task do porównywania źródeł BPP z PBN.

    Raportuje postęp przez mechanizm update_state Celery.

    Args:
        min_rok: Minimalny rok do porównania
        clear_existing: Czy wyczyścić istniejące rozbieżności przed porównaniem

    Returns:
        dict ze statystykami
    """
    from bpp.models import Zrodlo

    from .models import KomparatorZrodelMeta
    from .utils import KomparatorZrodelPBN, aktualizuj_brakujace_dyscypliny_pbn

    task_id = self.request.id
    cache_key = f"komparator_zrodel_progress_{task_id}"

    try:
        cache.set(
            cache_key,
            {
                "status": "PROGRESS",
                "current": 0,
                "total": 0,
                "message": "Inicjalizacja...",
            },
            3600,
        )

        # Aktualizuj listę brakujących dyscyplin na początku
        aktualizuj_brakujace_dyscypliny_pbn()

        komparator = KomparatorZrodelPBN(
            min_rok=min_rok,
            clear_existing=clear_existing,
            show_progress=False,
        )

        total = Zrodlo.objects.exclude(pbn_uid_id=None).count()

        # Nadpisz metodę compare_zrodlo aby raportować postęp
        original_compare = komparator.compare_zrodlo

        def compare_with_progress(zrodlo):
            result = original_compare(zrodlo)

            if komparator.stats["processed"] % 10 == 0:
                progress = (
                    int((komparator.stats["processed"] / total) * 100)
                    if total > 0
                    else 0
                )
                cache.set(
                    cache_key,
                    {
                        "status": "PROGRESS",
                        "current": komparator.stats["processed"],
                        "total": total,
                        "message": f"Przetwarzanie... ({komparator.stats['processed']}/{total})",
                        "stats": komparator.stats,
                        "progress": progress,
                    },
                    3600,
                )

                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": komparator.stats["processed"],
                        "total": total,
                        "stats": komparator.stats,
                        "progress": progress,
                    },
                )

            return result

        komparator.compare_zrodlo = compare_with_progress
        stats = komparator.run()

        cache.set(
            cache_key,
            {
                "status": "SUCCESS",
                "message": "Porównywanie zakończone",
                "stats": stats,
            },
            3600,
        )

        return {
            "status": "SUCCESS",
            "stats": stats,
            "message": f"Przetworzono {stats['processed']} źródeł",
        }

    except Exception as e:
        logger.exception("Błąd podczas porównywania źródeł")
        cache.set(
            cache_key,
            {
                "status": "FAILURE",
                "message": str(e),
            },
            3600,
        )

        # Zaktualizuj metadane
        from .models import KomparatorZrodelMeta

        meta = KomparatorZrodelMeta.get_instance()
        meta.status = "error"
        meta.ostatni_blad = str(e)
        meta.save()

        raise


@shared_task(bind=True)
def aktualizuj_wszystkie_task(self, pks, typ="oba", user_id=None):
    """
    Celery task do aktualizacji wszystkich źródeł z rozbieżnościami.

    Args:
        pks: Lista PK obiektów RozbieznoscZrodlaPBN
        typ: Typ aktualizacji ('punkty', 'dyscypliny', 'oba')
        user_id: ID użytkownika wykonującego aktualizację

    Returns:
        dict ze statystykami (updated, errors, total)
    """
    from bpp.models import BppUser

    from .models import RozbieznoscZrodlaPBN
    from .update_utils import aktualizuj_zrodlo_z_pbn

    task_id = self.request.id
    cache_key = f"komparator_zrodel_update_{task_id}"

    total = len(pks)
    updated = 0
    errors = 0

    user = None
    if user_id:
        try:
            user = BppUser.objects.get(pk=user_id)
        except BppUser.DoesNotExist:
            pass

    aktualizuj_punkty = typ in ["punkty", "oba"]
    aktualizuj_dyscypliny = typ in ["dyscypliny", "oba"]

    for idx, pk in enumerate(pks, 1):
        try:
            rozbieznosc = RozbieznoscZrodlaPBN.objects.select_related("zrodlo").get(
                pk=pk
            )
            zmieniono = aktualizuj_zrodlo_z_pbn(
                rozbieznosc.zrodlo,
                rozbieznosc.rok,
                aktualizuj_punkty=aktualizuj_punkty,
                aktualizuj_dyscypliny=aktualizuj_dyscypliny,
                user=user,
            )
            if zmieniono:
                updated += 1
        except RozbieznoscZrodlaPBN.DoesNotExist:
            logger.warning(f"Rozbieżność o pk={pk} nie istnieje")
            errors += 1
        except Exception as e:
            logger.exception(f"Błąd aktualizacji pk={pk}")
            rollbar.report_exc_info(sys.exc_info())
            # Store error in Meta object
            from .models import KomparatorZrodelMeta

            meta = KomparatorZrodelMeta.get_instance()
            meta.ostatni_blad = f"pk={pk}: {e}"
            meta.save(update_fields=["ostatni_blad"])
            errors += 1

        # Aktualizuj postęp co 5 elementów lub na końcu
        if idx % 5 == 0 or idx == total:
            progress = int((idx / total) * 100) if total > 0 else 0
            cache.set(
                cache_key,
                {
                    "status": "PROGRESS",
                    "current": idx,
                    "total": total,
                    "updated": updated,
                    "errors": errors,
                    "progress": progress,
                },
                3600,
            )

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": idx,
                    "total": total,
                    "updated": updated,
                    "errors": errors,
                    "progress": progress,
                },
            )

    return {
        "updated": updated,
        "errors": errors,
        "total": total,
        "message": f"Zaktualizowano {updated} źródeł",
    }


def get_task_status(task_id):
    """
    Pobiera status zadania z cache lub Celery.

    Args:
        task_id: ID zadania Celery

    Returns:
        dict ze statusem zadania
    """
    # Najpierw sprawdź cache
    for prefix in ["komparator_zrodel_progress_", "komparator_zrodel_update_"]:
        cache_key = f"{prefix}{task_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

    # Jeśli nie ma w cache, sprawdź w Celery
    result = AsyncResult(task_id)

    if result.state == "PENDING":
        return {"status": "PENDING", "message": "Zadanie oczekuje..."}
    elif result.state == "PROGRESS":
        return {
            "status": "PROGRESS",
            "current": result.info.get("current", 0) if result.info else 0,
            "total": result.info.get("total", 0) if result.info else 0,
            "progress": result.info.get("progress", 0) if result.info else 0,
            "stats": result.info.get("stats", {}) if result.info else {},
        }
    elif result.state == "SUCCESS":
        return {
            "status": "SUCCESS",
            "message": result.result.get("message", "Zakończone")
            if result.result
            else "Zakończone",
            "stats": result.result.get("stats", {}) if result.result else {},
            "updated": result.result.get("updated", 0) if result.result else 0,
            "errors": result.result.get("errors", 0) if result.result else 0,
        }
    elif result.state == "FAILURE":
        return {"status": "FAILURE", "message": str(result.info)}
    else:
        return {"status": result.state, "message": "Status nieznany"}
