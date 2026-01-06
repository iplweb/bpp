"""Taski optymalizacji dyscyplin."""

import logging
import traceback
from datetime import datetime
from decimal import Decimal

from celery import chord, group, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from celery_singleton import Singleton

from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from ewaluacja_optymalizacja.core import solve_discipline

from .helpers import (
    _collect_ids_to_unpin,
    _create_optimization_snapshot,
    _perform_batch_unpinning,
    _validate_all_disciplines_optimized,
    _wait_for_denorm,
)

logger = logging.getLogger(__name__)


@shared_task(
    soft_time_limit=600,  # 10 minutes - raises SoftTimeLimitExceeded
    time_limit=660,  # 11 minutes - hard kill
)
def solve_single_discipline_task(
    uczelnia_id, dyscyplina_id, liczba_n, algorithm_mode="two-phase"
):
    """
    Uruchamia optymalizację dla pojedynczej dyscypliny.

    To zadanie jest wywoływane równolegle dla każdej dyscypliny przez solve_all_reported_disciplines.

    Args:
        uczelnia_id: ID uczelni
        dyscyplina_id: ID dyscypliny naukowej
        liczba_n: wartość liczby N dla tej dyscypliny
        algorithm_mode: "two-phase" (default) or "single-phase"

    Returns:
        Dictionary z wynikami optymalizacji dla tej dyscypliny
    """
    from bpp.models import Dyscyplina_Naukowa, Uczelnia
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_optymalizacja.core import is_low_mono
    from ewaluacja_optymalizacja.models import (
        OptimizationAuthorResult,
        OptimizationPublication,
        OptimizationRun,
    )

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)
    dyscyplina = Dyscyplina_Naukowa.objects.get(pk=dyscyplina_id)
    dyscyplina_nazwa = dyscyplina.nazwa

    discipline_result = {
        "dyscyplina_id": dyscyplina.pk,
        "dyscyplina_nazwa": dyscyplina_nazwa,
        "liczba_n": float(liczba_n),
        "status": "running",
    }

    try:
        logger.info(f"Starting optimization for discipline: {dyscyplina_nazwa}")

        # Usuń stare optymalizacje dla tej dyscypliny
        deleted_count = OptimizationRun.objects.filter(
            dyscyplina_naukowa=dyscyplina
        ).delete()[0]
        if deleted_count > 0:
            logger.info(
                f"Deleted {deleted_count} old optimization runs for {dyscyplina_nazwa}"
            )

        # Uruchom optymalizację dla tej dyscypliny
        optimization_results = solve_discipline(
            dyscyplina_nazwa=dyscyplina_nazwa,
            verbose=False,
            log_callback=None,
            liczba_n=float(liczba_n),
            algorithm_mode=algorithm_mode,
        )

        logger.info(
            f"Optimization completed for {dyscyplina_nazwa}: "
            f"{optimization_results.total_points} points, "
            f"{optimization_results.total_publications} publications"
        )

        # Zapisz wyniki do bazy danych
        opt_run = OptimizationRun.objects.create(
            dyscyplina_naukowa=dyscyplina,
            uczelnia=uczelnia,
            status="completed",
            total_points=Decimal(str(optimization_results.total_points)),
            total_slots=Decimal(str(optimization_results.total_slots)),
            total_publications=optimization_results.total_publications,
            low_mono_count=optimization_results.low_mono_count,
            low_mono_percentage=Decimal(str(optimization_results.low_mono_percentage)),
            validation_passed=optimization_results.validation_passed,
            is_optimal=optimization_results.is_optimal,
            finished_at=datetime.now(),
        )

        # Zapisz wyniki autorów i publikacji
        for author_id, author_data in optimization_results.authors.items():
            selected_pubs = author_data["selected_pubs"]
            limits = author_data["limits"]

            # Pobierz rodzaj_autora dla tego autora (może być wiele rekordów - bierzemy pierwszy)
            record = (
                IloscUdzialowDlaAutoraZaCalosc.objects.filter(
                    autor_id=author_id, dyscyplina_naukowa=dyscyplina
                )
                .order_by("-ilosc_udzialow")
                .first()
            )
            rodzaj_autora = record.rodzaj_autora if record else None

            total_points = sum(p.points for p in selected_pubs)
            total_slots = sum(p.base_slots for p in selected_pubs)
            mono_slots = sum(
                p.base_slots for p in selected_pubs if p.kind == "monography"
            )

            author_result = OptimizationAuthorResult.objects.create(
                optimization_run=opt_run,
                autor_id=author_id,
                rodzaj_autora=rodzaj_autora,
                total_points=Decimal(str(total_points)),
                total_slots=Decimal(str(total_slots)),
                mono_slots=Decimal(str(mono_slots)),
                slot_limit_total=Decimal(str(limits["total"])),
                slot_limit_mono=Decimal(str(limits["mono"])),
            )

            # Zapisz publikacje dla tego autora
            for pub in selected_pubs:
                OptimizationPublication.objects.create(
                    author_result=author_result,
                    rekord_id=pub.id,
                    kind=pub.kind,
                    points=Decimal(str(pub.points)),
                    slots=Decimal(str(pub.base_slots)),
                    is_low_mono=is_low_mono(pub),
                    author_count=pub.author_count,
                )

        discipline_result["status"] = "completed"
        discipline_result["optimization_run_id"] = opt_run.pk
        discipline_result["total_points"] = float(optimization_results.total_points)
        discipline_result["total_publications"] = (
            optimization_results.total_publications
        )

        logger.info(f"Successfully saved optimization results for {dyscyplina_nazwa}")

    except SoftTimeLimitExceeded:
        # Handle timeout - discipline calculation took too long
        logger.error(f"Timeout: discipline {dyscyplina_nazwa} took too long (>10 min)")

        discipline_result["status"] = "failed"
        discipline_result["error"] = "Przekroczono limit czasu (10 minut)"

        # Save timeout failure to database
        try:
            OptimizationRun.objects.create(
                dyscyplina_naukowa=dyscyplina,
                uczelnia=uczelnia,
                status="failed",
                notes="Przekroczono limit czasu obliczeń (10 minut). "
                "Spróbuj ponownie lub sprawdź logi systemu.",
                finished_at=datetime.now(),
            )
        except Exception as db_error:
            logger.error(f"Failed to save timeout error to database: {db_error}")

    except Exception as e:
        # Log full traceback for debugging
        tb = traceback.format_exc()
        logger.error(
            f"Failed to optimize discipline {dyscyplina_nazwa}: {e}\n"
            f"Full traceback:\n{tb}"
        )

        discipline_result["status"] = "failed"
        discipline_result["error"] = f"{type(e).__name__}: {str(e)}"
        discipline_result["traceback"] = tb

        # Zapisz failed run do bazy danych
        try:
            OptimizationRun.objects.create(
                dyscyplina_naukowa=dyscyplina,
                uczelnia=uczelnia,
                status="failed",
                notes=f"Error: {type(e).__name__}: {str(e)}\n\nTraceback:\n{tb}",
                finished_at=datetime.now(),
            )
        except Exception as db_error:
            logger.error(f"Failed to save error to database: {db_error}")

    return discipline_result


@shared_task
def finalize_browser_recalc(results, uczelnia_id):
    """Callback wywoływany przez chord po zakończeniu wszystkich optymalizacji.

    Aktualizuje StatusPrzegladarkaRecalc oraz StatusOptymalizacjiBulk,
    aby użytkownik widział poprawny status nawet po odświeżeniu strony.
    """
    from django.utils import timezone

    from ewaluacja_optymalizacja.models import (
        StatusOptymalizacjiBulk,
        StatusPrzegladarkaRecalc,
    )

    logger.info(f"finalize_browser_recalc called for uczelnia_id={uczelnia_id}")

    status = StatusPrzegladarkaRecalc.get_or_create()
    if status.w_trakcie:
        status.zakoncz("Przeliczanie zakończone pomyślnie")
        logger.info("StatusPrzegladarkaRecalc marked as completed")

    # Aktualizuj również timestamp na stronie głównej
    status_bulk = StatusOptymalizacjiBulk.get_or_create()
    status_bulk.data_zakonczenia = timezone.now()
    status_bulk.save(update_fields=["data_zakonczenia"])
    logger.info("StatusOptymalizacjiBulk.data_zakonczenia updated")

    return {"uczelnia_id": uczelnia_id, "completed": True}


@shared_task(base=Singleton, unique_on=["uczelnia_id"], lock_expiry=3600, bind=True)
def solve_all_reported_disciplines(self, uczelnia_id, algorithm_mode="two-phase"):
    """
    Uruchamia optymalizację dla wszystkich dyscyplin raportowanych (>= 12 slotów).

    Każda dyscyplina jest przetwarzana równolegle w osobnym zadaniu Celery.
    Zadanie to tylko uruchamia grupę podzadań i natychmiast zwraca wynik.

    Status wykonywanych zadań można śledzić poprzez:
    - OptimizationRun records w bazie danych
    - LiczbaNDlaUczelni dla uczelni (określa listę dyscyplin)

    Używa celery-singleton aby zapewnić, że tylko jedno zadanie dla danej uczelni
    może być uruchomione jednocześnie.

    Args:
        uczelnia_id: ID uczelni dla której wykonać optymalizację
        algorithm_mode: "two-phase" (default) or "single-phase"

    Returns:
        Dictionary z podstawowymi informacjami o uruchomionych zadaniach
    """
    from bpp.models import Uczelnia

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    # Pobierz wszystkie dyscypliny raportowane (>= 12 slotów)
    raportowane_dyscypliny = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    discipline_count = raportowane_dyscypliny.count()
    started_at = datetime.now().isoformat()

    logger.info(
        f"Starting parallel optimization for {uczelnia}: "
        f"{discipline_count} disciplines to process"
    )

    if discipline_count == 0:
        logger.warning(f"No disciplines found for {uczelnia} with liczba_n >= 12")
        return {
            "uczelnia_id": uczelnia_id,
            "uczelnia_nazwa": str(uczelnia),
            "started_at": started_at,
            "total_disciplines": 0,
            "finished_at": datetime.now().isoformat(),
        }

    # Stwórz listę zadań dla każdej dyscypliny
    tasks = []

    for liczba_n_obj in raportowane_dyscypliny:
        dyscyplina = liczba_n_obj.dyscyplina_naukowa
        # Używamy liczba_n_ostateczna (N - sankcje) dla optymalizacji
        task = solve_single_discipline_task.s(
            uczelnia_id,
            dyscyplina.pk,
            float(liczba_n_obj.liczba_n_ostateczna),
            algorithm_mode,
        )
        tasks.append(task)

    logger.info(f"Created {len(tasks)} parallel tasks, launching chord...")

    # Uruchom wszystkie zadania równolegle używając chord()
    # Po zakończeniu wszystkich tasków, chord wywoła finalize_browser_recalc
    workflow = chord(tasks)(finalize_browser_recalc.s(uczelnia_id=uczelnia_id))

    # Pobierz task_ids z chord header (grupy)
    task_ids = []
    if hasattr(workflow, "parent") and workflow.parent:
        task_ids = [t.id for t in workflow.parent.results]

    logger.info(
        f"Chord launched with {len(task_ids)} tasks + callback. "
        f"Tasks are running in background. "
        f"finalize_browser_recalc will be called when all tasks complete."
    )

    # Zwróć podstawowe informacje - NIE CZEKAMY NA ZAKOŃCZENIE!
    return {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "started_at": started_at,
        "total_disciplines": discipline_count,
        "task_ids": task_ids,
        "callback_task_id": workflow.id,
    }


def _run_bulk_optimization(
    task,
    uczelnia,
    dyscypliny_ids,
    discipline_count,
    meta_extra,
    logger_func,
    algorithm_mode="two-phase",
):
    """Run bulk optimization for all disciplines."""
    from time import sleep

    from ewaluacja_optymalizacja.models import (
        OptimizationAuthorResult,
        OptimizationPublication,
        OptimizationRun,
    )

    # Delete existing OptimizationRun records
    logger_func(f"Deleting existing OptimizationRun records for uczelnia {uczelnia.pk}")
    deleted_count = OptimizationRun.objects.filter(uczelnia=uczelnia).delete()[0]
    logger_func(f"Deleted {deleted_count} OptimizationRun records")

    # Launch parallel optimization tasks
    raportowane_dyscypliny = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    tasks = []
    for liczba_n_obj in raportowane_dyscypliny:
        dyscyplina = liczba_n_obj.dyscyplina_naukowa
        # Używamy liczba_n_ostateczna (N - sankcje) dla optymalizacji
        task_obj = solve_single_discipline_task.s(
            uczelnia.pk,
            dyscyplina.pk,
            float(liczba_n_obj.liczba_n_ostateczna),
            algorithm_mode,
        )
        tasks.append(task_obj)

    if tasks:
        job = group(tasks)
        job.apply_async()

    logger_func(
        f"Triggered {len(tasks)} parallel optimization tasks for {discipline_count} disciplines"
    )

    # Monitor progress through database
    max_wait = 1800  # Max 30 minutes
    waited = 0
    check_interval = 5

    while waited < max_wait:
        completed_count = OptimizationRun.objects.filter(
            uczelnia=uczelnia,
            dyscyplina_naukowa_id__in=dyscypliny_ids,
            status="completed",
        ).count()

        running_count = OptimizationRun.objects.filter(
            uczelnia=uczelnia,
            dyscyplina_naukowa_id__in=dyscypliny_ids,
            status="running",
        ).count()

        if discipline_count > 0:
            percent_complete = int((completed_count / discipline_count) * 100)
            progress = min(65 + int((completed_count / discipline_count) * 30), 95)
        else:
            percent_complete = 0
            progress = 65

        logger_func(
            f"Optimization progress: {completed_count}/{discipline_count} completed "
            f"({percent_complete}%), {running_count} running"
        )

        task.update_state(
            state="PROGRESS",
            meta={
                **meta_extra,
                "step": "optimization",
                "progress": progress,
                "message": f"Przeliczono {completed_count} z {discipline_count} dyscyplin "
                f"({percent_complete}%)",
                "running_optimizations": running_count,
                "completed_optimizations": completed_count,
                "total_optimizations": discipline_count,
            },
        )

        # Check if all completed and data is saved
        if completed_count == discipline_count:
            logger_func("All optimizations completed, verifying data integrity...")
            all_data_saved = True

            for liczba_n_obj in raportowane_dyscypliny:
                opt_run = (
                    OptimizationRun.objects.filter(
                        uczelnia=uczelnia,
                        dyscyplina_naukowa=liczba_n_obj.dyscyplina_naukowa,
                        status="completed",
                    )
                    .order_by("-started_at")
                    .first()
                )

                if opt_run:
                    author_results = OptimizationAuthorResult.objects.filter(
                        optimization_run=opt_run
                    ).exists()
                    publications = OptimizationPublication.objects.filter(
                        author_result__optimization_run=opt_run
                    ).exists()

                    if not (author_results and publications):
                        logger_func(
                            f"Data not fully saved for "
                            f"{liczba_n_obj.dyscyplina_naukowa.nazwa}: "
                            f"authors={author_results}, publications={publications}"
                        )
                        all_data_saved = False
                        break
                else:
                    logger_func(
                        f"No optimization run found for "
                        f"{liczba_n_obj.dyscyplina_naukowa.nazwa}"
                    )
                    all_data_saved = False
                    break

            if all_data_saved:
                logger_func("All optimization data verified in database")
                break

        sleep(check_interval)
        waited += check_interval


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id"],
    lock_expiry=7200,
    bind=True,
    time_limit=3600,
)
def optimize_and_unpin_task(self, uczelnia_id, algorithm_mode="two-phase"):
    """
    Zadanie które:
    1. Sprawdza czy wszystkie dyscypliny raportowane są przeliczone
    2. Tworzy snapshot obecnego stanu przypięć
    3. Odpina dyscypliny w pracach niewykazanych do ewaluacji
    4. Automatycznie przelicza punktację całej uczelni

    Args:
        uczelnia_id: ID uczelni dla której wykonać optymalizację
        algorithm_mode: "two-phase" (default) or "single-phase"

    Returns:
        Dictionary z informacją o wykonanych operacjach
    """
    from django.db.models import Sum

    from bpp.models import (
        Uczelnia,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )
    from ewaluacja_optymalizacja.models import (
        OptimizationAuthorResult,
        OptimizationRun,
    )

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(f"Starting optimize_and_unpin_task for {uczelnia}")

    # Update task state
    self.update_state(state="PROGRESS", meta={"step": "validation", "progress": 0})

    # 1. Validation
    _validate_all_disciplines_optimized(uczelnia, logger.info)

    # Update task state
    self.update_state(state="PROGRESS", meta={"step": "snapshot", "progress": 10})

    # 2. Create snapshot
    snapshot, suma_punktow_przed, suma_slotow_przed = _create_optimization_snapshot(
        uczelnia, logger.info
    )

    # Get initial pinned counts for progress tracking
    total_pinned_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
        przypieta=True
    ).count()
    total_pinned_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
        przypieta=True
    ).count()

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "unpinning",
            "progress": 20,
            "total_pinned_ciagle": total_pinned_ciagle,
            "total_pinned_zwarte": total_pinned_zwarte,
        },
    )

    # 3. Collect IDs to unpin
    autorzy_z_wynikami = set(
        OptimizationAuthorResult.objects.filter(
            optimization_run__uczelnia=uczelnia, optimization_run__status="completed"
        ).values_list("autor_id", flat=True)
    )

    logger.info(f"Found {len(autorzy_z_wynikami)} authors with optimization results")

    ids_to_unpin_ciagle, ids_to_unpin_zwarte = _collect_ids_to_unpin(
        uczelnia, autorzy_z_wynikami, logger.warning
    )

    # 4. Perform batch unpinning (with progress tracking)
    odpięte_ciagle, odpięte_zwarte = _perform_batch_unpinning(
        ids_to_unpin_ciagle, ids_to_unpin_zwarte, logger.info, task=self
    )

    # Get current pinned counts after unpinning
    current_pinned_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
        przypieta=True
    ).count()
    current_pinned_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
        przypieta=True
    ).count()

    # 5. Wait for denormalization
    logger.info("Starting denormalization rebuild")
    _wait_for_denorm(
        self,
        progress_start=50,
        progress_range=40,
        meta_extra={
            "unpinned_ciagle": odpięte_ciagle,
            "unpinned_zwarte": odpięte_zwarte,
            "total_pinned_ciagle": total_pinned_ciagle,
            "total_pinned_zwarte": total_pinned_zwarte,
            "current_pinned_ciagle": current_pinned_ciagle,
            "current_pinned_zwarte": current_pinned_zwarte,
        },
        logger_func=logger.info,
    )

    # 6. Run bulk optimization
    logger.info("Starting bulk optimization recalculation")

    liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    discipline_count = liczba_n_raportowane.count()
    dyscypliny_ids = list(
        liczba_n_raportowane.values_list("dyscyplina_naukowa_id", flat=True)
    )

    self.update_state(
        state="PROGRESS",
        meta={
            "step": "optimization",
            "progress": 65,
            "message": "Rozpoczynanie przeliczania optymalizacji...",
            "completed_optimizations": 0,
            "total_optimizations": discipline_count,
            "unpinned_ciagle": odpięte_ciagle,
            "unpinned_zwarte": odpięte_zwarte,
            "total_pinned_ciagle": total_pinned_ciagle,
            "total_pinned_zwarte": total_pinned_zwarte,
            "current_pinned_ciagle": current_pinned_ciagle,
            "current_pinned_zwarte": current_pinned_zwarte,
        },
    )

    _run_bulk_optimization(
        self,
        uczelnia,
        dyscypliny_ids,
        discipline_count,
        meta_extra={
            "unpinned_ciagle": odpięte_ciagle,
            "unpinned_zwarte": odpięte_zwarte,
            "total_pinned_ciagle": total_pinned_ciagle,
            "total_pinned_zwarte": total_pinned_zwarte,
            "current_pinned_ciagle": current_pinned_ciagle,
            "current_pinned_zwarte": current_pinned_zwarte,
        },
        logger_func=logger.info,
        algorithm_mode=algorithm_mode,
    )

    # 7. Calculate final results (after optimization)
    suma_punktow_po = (
        OptimizationRun.objects.filter(uczelnia=uczelnia, status="completed").aggregate(
            suma=Sum("total_points")
        )["suma"]
        or 0
    )

    suma_slotow_po = (
        OptimizationRun.objects.filter(uczelnia=uczelnia, status="completed").aggregate(
            suma=Sum("total_slots")
        )["suma"]
        or 0
    )

    logger.info(
        f"Optimization complete. Points before: {suma_punktow_przed}, "
        f"after: {suma_punktow_po}. Slots before: {suma_slotow_przed}, "
        f"after: {suma_slotow_po}"
    )

    result = {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "snapshot_id": snapshot.pk,
        "unpinned_ciagle": odpięte_ciagle,
        "unpinned_zwarte": odpięte_zwarte,
        "unpinned_total": odpięte_ciagle + odpięte_zwarte,
        "points_before": float(suma_punktow_przed),
        "points_after": float(suma_punktow_po),
        "slots_before": float(suma_slotow_przed),
        "slots_after": float(suma_slotow_po),
        "completed_at": datetime.now().isoformat(),
    }

    return result
