import logging
import traceback
from datetime import datetime
from decimal import Decimal

from celery import group, shared_task
from celery_singleton import Singleton
from django.db.models import F

from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from ewaluacja_optymalizacja.core import solve_discipline

logger = logging.getLogger(__name__)


@shared_task
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
        task = solve_single_discipline_task.s(
            uczelnia_id, dyscyplina.pk, float(liczba_n_obj.liczba_n), algorithm_mode
        )
        tasks.append(task)

    logger.info(f"Created {len(tasks)} parallel tasks, launching group...")

    # Uruchom wszystkie zadania równolegle używając group()
    job = group(tasks)
    result_group = job.apply_async()

    # Zbierz task_ids z grupy
    task_ids = [r.id for r in result_group.results]

    logger.info(
        f"Group launched with {len(task_ids)} tasks. "
        f"Tasks are running in background. "
        f"Monitor progress via OptimizationRun records in database."
    )

    # Zwróć podstawowe informacje - NIE CZEKAMY NA ZAKOŃCZENIE!
    return {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "started_at": started_at,
        "total_disciplines": discipline_count,
        "task_ids": task_ids,
    }


def _validate_all_disciplines_optimized(uczelnia, logger_func):
    """Validate that all reported disciplines have completed optimization."""
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
    from ewaluacja_optymalizacja.models import OptimizationRun

    liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    )

    if liczba_n_raportowane.count() == 0:
        raise ValueError("Brak dyscyplin raportowanych (liczba N >= 12)")

    for liczba_n_obj in liczba_n_raportowane:
        if not OptimizationRun.objects.filter(
            dyscyplina_naukowa=liczba_n_obj.dyscyplina_naukowa,
            uczelnia=uczelnia,
            status="completed",
        ).exists():
            raise ValueError(
                f"Dyscyplina {liczba_n_obj.dyscyplina_naukowa.nazwa} "
                f"nie ma wykonanej optymalizacji"
            )

    logger_func(
        f"Validation passed - all {liczba_n_raportowane.count()} disciplines have optimization"
    )


def _create_optimization_snapshot(uczelnia, logger_func):
    """Create snapshot before optimization with unpinning."""
    from django.db.models import Sum

    from snapshot_odpiec.models import SnapshotOdpiec

    from .models import OptimizationRun

    suma_punktow_przed = (
        OptimizationRun.objects.filter(uczelnia=uczelnia, status="completed").aggregate(
            suma=Sum("total_points")
        )["suma"]
        or 0
    )

    suma_slotow_przed = (
        OptimizationRun.objects.filter(uczelnia=uczelnia, status="completed").aggregate(
            suma=Sum("total_slots")
        )["suma"]
        or 0
    )

    snapshot_comment = (
        f"Snapshot przed optymalizacją z odpinaniem. "
        f"Suma punktów: {suma_punktow_przed}, "
        f"Suma slotów: {suma_slotow_przed}"
    )

    snapshot = SnapshotOdpiec.objects.create(owner=None, comment=snapshot_comment)

    logger_func(f"Created snapshot {snapshot.pk}: {snapshot_comment}")
    return snapshot, suma_punktow_przed, suma_slotow_przed


def _collect_ids_to_unpin(uczelnia, autorzy_z_wynikami, logger_func):
    """Collect IDs of publications to unpin.

    Only considers publications from years 2022-2025 (rok >= 2022 and rok < 2026).
    Unpins publications that are either:
    - Not in optimization results, OR
    - In optimization results but with slot < 1.0
    """
    from decimal import Decimal

    from django.contrib.contenttypes.models import ContentType

    from bpp.models import (
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte,
        Wydawnictwo_Zwarte_Autor,
    )

    from .models import OptimizationPublication

    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    ids_to_unpin_ciagle = []
    ids_to_unpin_zwarte = []

    for autor_id in autorzy_z_wynikami:
        # Build a lookup dict: rekord_id -> slots from optimization results
        autor_wykazane_prace = {
            rekord_id: slots
            for rekord_id, slots in OptimizationPublication.objects.filter(
                author_result__autor_id=autor_id,
                author_result__optimization_run__uczelnia=uczelnia,
                author_result__optimization_run__status="completed",
            ).values_list("rekord_id", "slots")
        }

        # Wydawnictwa ciągłe - only years 2022-2025
        for udział in Wydawnictwo_Ciagle_Autor.objects.filter(
            autor_id=autor_id,
            przypieta=True,
            rekord__rok__gte=2022,
            rekord__rok__lt=2026,
        ).select_related("rekord"):
            rekord_id = (ct_ciagle.pk, udział.rekord.pk)

            # Unpin if not in optimization results OR slot < 1.0
            slots = autor_wykazane_prace.get(rekord_id)
            if slots is None or slots < Decimal("1.0"):
                ids_to_unpin_ciagle.append(udział.pk)

        # Wydawnictwa zwarte - only years 2022-2025
        for udział in Wydawnictwo_Zwarte_Autor.objects.filter(
            autor_id=autor_id,
            przypieta=True,
            rekord__rok__gte=2022,
            rekord__rok__lt=2026,
        ).select_related("rekord"):
            rekord_id = (ct_zwarte.pk, udział.rekord.pk)

            # Unpin if not in optimization results OR slot < 1.0
            slots = autor_wykazane_prace.get(rekord_id)
            if slots is None or slots < Decimal("1.0"):
                ids_to_unpin_zwarte.append(udział.pk)

    logger_func(
        f"Prepared to unpin {len(ids_to_unpin_ciagle)} Wydawnictwo_Ciagle_Autor records "
        f"and {len(ids_to_unpin_zwarte)} Wydawnictwo_Zwarte_Autor records"
    )

    return ids_to_unpin_ciagle, ids_to_unpin_zwarte


def _perform_batch_unpinning(ids_to_unpin_ciagle, ids_to_unpin_zwarte, logger_func):
    """Perform batch unpinning operations."""
    from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

    if ids_to_unpin_ciagle:
        batch_size = 500
        for i in range(0, len(ids_to_unpin_ciagle), batch_size):
            batch_ids = ids_to_unpin_ciagle[i : i + batch_size]
            Wydawnictwo_Ciagle_Autor.objects.filter(pk__in=batch_ids).update(
                przypieta=False
            )
            logger_func(
                f"Unpinned Wydawnictwo_Ciagle_Autor batch {i // batch_size + 1} of "
                f"{(len(ids_to_unpin_ciagle) + batch_size - 1) // batch_size}"
            )

    logger_func(f"Unpinned {len(ids_to_unpin_ciagle)} Wydawnictwo_Ciagle_Autor records")

    if ids_to_unpin_zwarte:
        batch_size = 500
        for i in range(0, len(ids_to_unpin_zwarte), batch_size):
            batch_ids = ids_to_unpin_zwarte[i : i + batch_size]
            Wydawnictwo_Zwarte_Autor.objects.filter(pk__in=batch_ids).update(
                przypieta=False
            )
            logger_func(
                f"Unpinned Wydawnictwo_Zwarte_Autor batch {i // batch_size + 1} of "
                f"{(len(ids_to_unpin_zwarte) + batch_size - 1) // batch_size}"
            )

    logger_func(f"Unpinned {len(ids_to_unpin_zwarte)} Wydawnictwo_Zwarte_Autor records")

    return len(ids_to_unpin_ciagle), len(ids_to_unpin_zwarte)


def _wait_for_denorm(task, progress_start, progress_range, meta_extra, logger_func):
    """Wait for denormalization to complete."""
    from time import sleep

    from denorm.models import DirtyInstance
    from denorm.tasks import flush_via_queue

    # Trigger denorm processing via Celery queue
    flush_via_queue.delay()
    logger_func("Triggered denorm flush via queue")

    max_wait = 600  # Max 10 minutes
    waited = 0
    check_interval = 5

    while DirtyInstance.objects.count() > 0 and waited < max_wait:
        sleep(check_interval)
        waited += check_interval
        dirty_count = DirtyInstance.objects.count()

        # Update progress
        progress = min(progress_start + (waited / max_wait * progress_range), 90)
        task.update_state(
            state="PROGRESS",
            meta={
                **meta_extra,
                "step": "denorm",
                "progress": progress,
                "dirty_count": dirty_count,
            },
        )

        logger_func(f"Waiting for denormalization... {dirty_count} objects remaining")


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

    from celery import group

    from .models import (
        OptimizationAuthorResult,
        OptimizationPublication,
        OptimizationRun,
    )

    # Delete existing OptimizationRun records
    logger_func(f"Deleting existing OptimizationRun records for uczelnia {uczelnia.pk}")
    deleted_count = OptimizationRun.objects.filter(uczelnia=uczelnia).delete()[0]
    logger_func(f"Deleted {deleted_count} OptimizationRun records")

    # Launch parallel optimization tasks
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    raportowane_dyscypliny = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    tasks = []
    for liczba_n_obj in raportowane_dyscypliny:
        dyscyplina = liczba_n_obj.dyscyplina_naukowa
        task_obj = solve_single_discipline_task.s(
            uczelnia.pk, dyscyplina.pk, float(liczba_n_obj.liczba_n), algorithm_mode
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
            f"Optimization progress: {completed_count}/{discipline_count} completed ({percent_complete}%), "
            f"{running_count} running"
        )

        task.update_state(
            state="PROGRESS",
            meta={
                **meta_extra,
                "step": "optimization",
                "progress": progress,
                "message": f"Przeliczono {completed_count} z {discipline_count} dyscyplin ({percent_complete}%)",
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
                            f"Data not fully saved for {liczba_n_obj.dyscyplina_naukowa.nazwa}: "
                            f"authors={author_results}, publications={publications}"
                        )
                        all_data_saved = False
                        break
                else:
                    logger_func(
                        f"No optimization run found for {liczba_n_obj.dyscyplina_naukowa.nazwa}"
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
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    from .models import (
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

    # 4. Perform batch unpinning
    odpięte_ciagle, odpięte_zwarte = _perform_batch_unpinning(
        ids_to_unpin_ciagle, ids_to_unpin_zwarte, logger.info
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


def _reset_pins_for_authors(autorzy_ids, task, snapshot_pk, logger_func):
    """Reset pins for all authors in years 2022-2025."""
    from django.db.models import Q

    from bpp.models import (
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    base_filter = Q(
        rekord__rok__gte=2022, rekord__rok__lte=2025, autor_id__in=autorzy_ids
    )

    updated_count = 0

    # Wydawnictwo Ciągłe Autor
    count_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(base_filter).update(
        przypieta=True
    )
    updated_count += count_ciagle
    logger_func(
        f"Reset {count_ciagle} pins in Wydawnictwo_Ciagle_Autor for {len(autorzy_ids)} authors"
    )

    task.update_state(
        state="PROGRESS",
        meta={
            "step": "resetting",
            "progress": 50,
            "snapshot_id": snapshot_pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
        },
    )

    # Wydawnictwo Zwarte Autor
    count_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(base_filter).update(
        przypieta=True
    )
    updated_count += count_zwarte
    logger_func(
        f"Reset {count_zwarte} pins in Wydawnictwo_Zwarte_Autor for {len(autorzy_ids)} authors"
    )

    task.update_state(
        state="PROGRESS",
        meta={
            "step": "resetting",
            "progress": 70,
            "snapshot_id": snapshot_pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
            "reset_zwarte": count_zwarte,
        },
    )

    # Patent Autor
    count_patent = Patent_Autor.objects.filter(base_filter).update(przypieta=True)
    updated_count += count_patent
    logger_func(
        f"Reset {count_patent} pins in Patent_Autor for {len(autorzy_ids)} authors"
    )

    task.update_state(
        state="PROGRESS",
        meta={
            "step": "waiting_denorm",
            "progress": 80,
            "snapshot_id": snapshot_pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
            "reset_zwarte": count_zwarte,
            "reset_patent": count_patent,
            "total_reset": updated_count,
        },
    )

    logger_func(
        f"Reset complete. Total pins reset: {updated_count} "
        f"(Ciągłe: {count_ciagle}, Zwarte: {count_zwarte}, Patent: {count_patent})"
    )

    return count_ciagle, count_zwarte, count_patent, updated_count


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id"],
    lock_expiry=3600,
    bind=True,
    time_limit=1800,
)
def reset_all_pins_task(self, uczelnia_id, algorithm_mode="two-phase"):
    """
    Resetuje przypięcia dla wszystkich rekordów 2022-2025 gdzie autor ma dyscyplinę,
    jest zatrudniony i afiliuje.

    Args:
        uczelnia_id: ID uczelni dla której resetować przypięcia
        algorithm_mode: "two-phase" (default) or "single-phase"

    Returns:
        Dictionary z informacją o wykonanych operacjach
    """
    from django.db import transaction

    from bpp.models import (
        Autor_Dyscyplina,
        Uczelnia,
    )
    from snapshot_odpiec.models import SnapshotOdpiec

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(f"Starting reset_all_pins_task for {uczelnia}")

    # Update task state
    self.update_state(state="PROGRESS", meta={"step": "collecting", "progress": 10})

    # Pobierz wszystkich autorów którzy mają Autor_Dyscyplina w latach 2022-2025
    # dla dowolnej dyscypliny
    autorzy_ids = set(
        Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
        .values_list("autor_id", flat=True)
        .distinct()
    )

    logger.info(
        f"Found {len(autorzy_ids)} authors with Autor_Dyscyplina in years 2022-2025"
    )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "snapshot",
            "progress": 20,
            "total_authors": len(autorzy_ids),
        },
    )

    with transaction.atomic():
        # Utwórz snapshot przed resetowaniem
        snapshot = SnapshotOdpiec.objects.create(
            owner=None,  # System tworzy snapshot
            comment=f"przed resetem przypięć - wszystkie dyscypliny uczelni {uczelnia}",
        )

        logger.info(
            f"Created snapshot {snapshot.pk} before resetting pins for all disciplines "
            f"(uczelnia: {uczelnia})"
        )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "resetting",
            "progress": 30,
            "snapshot_id": snapshot.pk,
            "total_authors": len(autorzy_ids),
        },
    )

    # Reset pins for all models
    count_ciagle, count_zwarte, count_patent, updated_count = _reset_pins_for_authors(
        autorzy_ids, self, snapshot.pk, logger.info
    )

    # Wait for denormalization
    logger.info("Waiting for denormalization...")
    _wait_for_denorm(
        self,
        progress_start=80,
        progress_range=15,
        meta_extra={
            "snapshot_id": snapshot.pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
            "reset_zwarte": count_zwarte,
            "reset_patent": count_patent,
            "total_reset": updated_count,
        },
        logger_func=logger.info,
    )

    # Run bulk optimization after reset
    logger.info("Starting bulk optimization recalculation after reset")

    liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    discipline_count = liczba_n_raportowane.count()
    dyscypliny_ids = list(
        liczba_n_raportowane.values_list("dyscyplina_naukowa_id", flat=True)
    )

    if discipline_count > 0:
        self.update_state(
            state="PROGRESS",
            meta={
                "step": "optimization_start",
                "progress": 95,
                "snapshot_id": snapshot.pk,
                "total_reset": updated_count,
            },
        )

        _run_bulk_optimization(
            self,
            uczelnia,
            dyscypliny_ids,
            discipline_count,
            meta_extra={
                "snapshot_id": snapshot.pk,
                "total_reset": updated_count,
            },
            logger_func=logger.info,
            algorithm_mode=algorithm_mode,
        )

    result = {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "snapshot_id": snapshot.pk,
        "total_authors": len(autorzy_ids),
        "reset_ciagle": count_ciagle,
        "reset_zwarte": count_zwarte,
        "reset_patent": count_patent,
        "total_reset": updated_count,
        "optimizations_recalculated": discipline_count if discipline_count > 0 else 0,
        "completed_at": datetime.now().isoformat(),
    }

    return result


def simulate_unpinning_benefit(  # noqa: C901
    autor_assignment,
    autor_currently_using,
    dyscyplina_naukowa,
    metrics_before_cache=None,
):
    """
    Symuluje odpięcie pracy dla jednego autora i sprawdza czy instytucja zyskuje punkty.

    Args:
        autor_assignment: Obiekt *_Autor (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor)
                         reprezentujący przypięcie do odpinania
        autor_currently_using: Obiekt Autor który obecnie ma pracę w zebranych
        dyscyplina_naukowa: Obiekt Dyscyplina_Naukowa
        metrics_before_cache: dict (optional) - cache dla metryk "przed odpięciem" {publikacja.pk: results_before}
                             używany do optymalizacji - unika wielokrotnego przeliczania tych samych metryk

    Returns:
        dict: {
            'makes_sense': bool - True jeśli odpięcie ma sens (instytucja zyskuje więcej punktów niż traci),
            'punkty_roznica_a': Decimal - różnica punktów dla autora A (ujemna=strata, dodatnia=zysk),
            'sloty_roznica_a': Decimal - różnica slotów dla autora A (ujemna=strata, dodatnia=zysk),
            'punkty_roznica_b': Decimal - różnica punktów dla autora B (ujemna=strata, dodatnia=zysk),
            'sloty_roznica_b': Decimal - różnica slotów dla autora B (ujemna=strata, dodatnia=zysk),
        }
        lub None jeśli nie udało się przeprowadzić symulacji
    """
    from decimal import Decimal

    from django.db import transaction

    from bpp.models.sloty.core import IPunktacjaCacher
    from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

    try:
        # Cała symulacja w jednej transakcji
        with transaction.atomic():
            # KLUCZOWE: Oblicz ŚWIEŻE metryki PRZED odpięciem (z obecnym stanem przypięć)
            # Porównamy to z metrykami PO odpięciu - obie będą świeżo obliczone
            autor_a = autor_assignment.autor
            publikacja = autor_assignment.rekord

            # Symulacja w transakcji z savepoint
            sid = transaction.savepoint()

            try:
                # 1. Oblicz metryki PRZED odpięciem (świeża kalkulacja, z cache jeśli dostępny)
                publikacja_pk = publikacja.pk

                if (
                    metrics_before_cache is not None
                    and publikacja_pk in metrics_before_cache
                ):
                    # Cache hit - użyj zapisanych wyników
                    results_before = metrics_before_cache[publikacja_pk]
                    logger.debug(
                        f"Cache HIT dla publikacji {publikacja.tytul_oryginalny[:50]} (pk={publikacja_pk})"
                    )
                else:
                    # Cache miss - oblicz i zapisz
                    results_before = przelicz_metryki_dla_publikacji(publikacja)
                    if metrics_before_cache is not None:
                        metrics_before_cache[publikacja_pk] = results_before
                        logger.debug(
                            f"Cache MISS dla publikacji {publikacja.tytul_oryginalny[:50]} (pk={publikacja_pk}), zapisano"
                        )

                # Znajdź metryki dla autorów A i B w naszej dyscyplinie
                metryka_a_before = None
                metryka_b_before = None

                for autor, dyscyplina, metryka in results_before:
                    if (
                        autor.id == autor_a.id
                        and dyscyplina.id == dyscyplina_naukowa.id
                    ):
                        metryka_a_before = metryka
                    if (
                        autor.id == autor_currently_using.id
                        and dyscyplina.id == dyscyplina_naukowa.id
                    ):
                        metryka_b_before = metryka

                # Sprawdź czy znaleziono metryki dla B
                if metryka_b_before is None:
                    logger.warning(
                        f"Brak metryk PRZED dla autora B {autor_currently_using} w dyscyplinie {dyscyplina_naukowa}"
                    )
                    return None

                # Pobierz wartości (jeśli metryka_a_before == None, użyj 0)
                punkty_a_before = (
                    metryka_a_before.punkty_nazbierane
                    if metryka_a_before
                    else Decimal("0")
                )
                slot_a_before = (
                    metryka_a_before.slot_nazbierany
                    if metryka_a_before
                    else Decimal("0")
                )

                punkty_b_before = metryka_b_before.punkty_nazbierane
                slot_b_before = metryka_b_before.slot_nazbierany

                # 2. Odpnij dla Autora A
                autor_assignment.przypieta = False
                autor_assignment.save()

                # 3. Przebuduj cache punktacji
                cacher = IPunktacjaCacher(publikacja)
                cacher.removeEntries()
                cacher.rebuildEntries()

                # CRITICAL: Wymuś odświeżenie cache w Django ORM
                # W ramach savepoint PostgreSQL może mieć niezaktualizowane querysets
                from django.db import connection

                connection.cursor().execute("SELECT 1")  # Flush pending queries

                # 4. Przelicz metryki PO odpięciu (świeża kalkulacja)
                # Porównamy to z metrykami PRZED odpięciem - obie są świeżo obliczone
                results = przelicz_metryki_dla_publikacji(publikacja)

                # Znajdź metryki dla autorów A i B w naszej dyscyplinie
                metryka_a_after = None
                metryka_b_after = None

                for autor, dyscyplina, metryka in results:
                    if (
                        autor.id == autor_a.id
                        and dyscyplina.id == dyscyplina_naukowa.id
                    ):
                        metryka_a_after = metryka
                    if (
                        autor.id == autor_currently_using.id
                        and dyscyplina.id == dyscyplina_naukowa.id
                    ):
                        metryka_b_after = metryka

                # Sprawdź czy znaleziono metryki
                if metryka_b_after is None:
                    logger.warning(
                        f"Brak metryk PO dla autora B {autor_currently_using} w dyscyplinie {dyscyplina_naukowa}"
                    )
                    return None

                # Pobierz wartości (jeśli metryka_a_after == None, użyj 0)
                punkty_a_after = (
                    metryka_a_after.punkty_nazbierane
                    if metryka_a_after
                    else Decimal("0")
                )
                slot_a_after = (
                    metryka_a_after.slot_nazbierany if metryka_a_after else Decimal("0")
                )

                punkty_b_after = metryka_b_after.punkty_nazbierane
                slot_b_after = metryka_b_after.slot_nazbierany

                # Oblicz różnice (ujemne = strata, dodatnie = zysk)
                punkty_roznica_a = (
                    punkty_a_after - punkty_a_before
                )  # ujemne jeśli stracił
                sloty_roznica_a = slot_a_after - slot_a_before

                punkty_roznica_b = (
                    punkty_b_after - punkty_b_before
                )  # dodatnie jeśli zyskał
                sloty_roznica_b = slot_b_after - slot_b_before

                # KLUCZOWE: Jeśli praca NIE weszła dla A (praca_weszla==False),
                # to A nie straci punktów (bo i tak jej nie wykazywał)
                # Sprawdzamy to przez porównanie prac nazbieranych
                if metryka_a_before is not None:
                    rekord_id = publikacja.pk  # tuple (content_type_id, object_id)
                    prace_nazbierane_a = metryka_a_before.prace_nazbierane or []
                    # Konwertuj listy na tuple (JSONField zwraca listy)
                    prace_nazbierane_a_tuples = [
                        tuple(p) if isinstance(p, list) else p
                        for p in prace_nazbierane_a
                    ]
                    praca_byla_wykazana_dla_a = rekord_id in prace_nazbierane_a_tuples
                else:
                    praca_byla_wykazana_dla_a = False

                # Oblicz stratę A i zysk B
                if not praca_byla_wykazana_dla_a:
                    # Praca nie była wykazana - A nie straci nic
                    punkty_strata_a = Decimal("0")
                else:
                    # Praca była wykazana - A straci
                    punkty_strata_a = abs(punkty_roznica_a)

                punkty_zysk_b = (
                    punkty_roznica_b if punkty_roznica_b > 0 else Decimal("0")
                )

                # NOWE KRYTERIUM: Odpięcie ma sens gdy instytucja zyskuje więcej niż traci
                # (w granicach udziałów)
                makes_sense = punkty_zysk_b > punkty_strata_a

                logger.debug(
                    f"Symulacja odpięcia dla {autor_a} -> {autor_currently_using} (publikacja: {publikacja.tytul_oryginalny[:50]}): "
                    f"praca_byla_wykazana_dla_a={praca_byla_wykazana_dla_a}, "
                    f"A punkty ŚWIEŻE PRZED: {punkty_a_before} -> ŚWIEŻE PO: {punkty_a_after} (różnica: {punkty_roznica_a}), "
                    f"A strata punktów: {punkty_strata_a}, "
                    f"A sloty {slot_a_before} -> {slot_a_after} (różnica: {sloty_roznica_a}), "
                    f"B punkty ŚWIEŻE PRZED: {punkty_b_before} -> ŚWIEŻE PO: {punkty_b_after} (różnica: {punkty_roznica_b}), "
                    f"B zysk punktów: {punkty_zysk_b}, "
                    f"B sloty {slot_b_before} -> {slot_b_after} (różnica: {sloty_roznica_b}), "
                    f"makes_sense={makes_sense} (B zysk {punkty_zysk_b} > A strata {punkty_strata_a})"
                )

                return {
                    "makes_sense": makes_sense,
                    "punkty_roznica_a": punkty_roznica_a,
                    "sloty_roznica_a": sloty_roznica_a,
                    "punkty_roznica_b": punkty_roznica_b,
                    "sloty_roznica_b": sloty_roznica_b,
                }

            finally:
                # ZAWSZE rollback - przywróć stan przed symulacją
                transaction.savepoint_rollback(sid)

    except Exception as e:
        logger.error(f"Błąd podczas symulacji odpięcia: {e}", exc_info=True)
        # W przypadku błędu, zwracamy None
        return None


def _analyze_multi_author_works_impl(  # noqa: C901
    task, uczelnia_id, dyscyplina_id=None, min_slot_filled=0.8, progress_offset=0
):
    """
    Implementacja analizy prac wieloautorskich - wydzielona do wielokrotnego użycia.

    Args:
        task: Celery task object (self) do aktualizacji statusu
        uczelnia_id: ID uczelni
        dyscyplina_id: ID dyscypliny (opcjonalnie, jeśli None to wszystkie)
        min_slot_filled: Minimalny próg wypełnienia slotów (domyślnie 0.8 = 80%)
        progress_offset: Bazowy offset dla progressu (0-100)

    Returns:
        Dictionary z wynikami analizy
    """
    from decimal import Decimal

    from bpp.models import Uczelnia
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora_Query
    from ewaluacja_metryki.models import MetrykaAutora

    from .models import UnpinningOpportunity

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(
        f"Starting unpinning analysis for {uczelnia}, dyscyplina_id={dyscyplina_id}"
    )

    # Update task state - Stage 2 progress: 50-100% (offset + 0 to offset + 50)
    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "unpinning",
            "step": "loading_metrics",
            "progress": progress_offset + 5,  # 55% of total (10% of stage 2)
        },
    )

    # Filtruj metryki - szukamy autorów z PEŁNYMI slotami (>=80% wypełnienia)
    metryki_qs = MetrykaAutora.objects.select_related(
        "autor", "dyscyplina_naukowa"
    ).filter(slot_nazbierany__gte=F("slot_maksymalny") * Decimal(str(min_slot_filled)))

    if dyscyplina_id:
        metryki_qs = metryki_qs.filter(dyscyplina_naukowa_id=dyscyplina_id)

    # Stwórz słownik metryk: (autor_id, dyscyplina_id) -> MetrykaAutora
    metryki_dict = {}
    for metryka in metryki_qs:
        key = (metryka.autor_id, metryka.dyscyplina_naukowa_id)
        metryki_dict[key] = metryka

    logger.info(f"Loaded {len(metryki_dict)} metrics with unfilled slots")

    # Update progress
    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "unpinning",
            "step": "analyzing_works",
            "progress": progress_offset + 10,  # 60% of total (20% of stage 2)
            "metrics_loaded": len(metryki_dict),
        },
    )

    # Usuń stare wyniki dla tej uczelni
    if dyscyplina_id:
        UnpinningOpportunity.objects.filter(
            uczelnia=uczelnia, dyscyplina_naukowa_id=dyscyplina_id
        ).delete()
    else:
        UnpinningOpportunity.objects.filter(uczelnia=uczelnia).delete()

    # Przygotuj słownik: rekord_id -> [(autor_id, dyscyplina_id, slot, metryka)]
    works_by_rekord = {}

    for (autor_id, dyscyplina_id_key), metryka in metryki_dict.items():
        # Konwertuj listy z JSONField na tuple dla porównania
        # (JSONField serializuje tuple jako JSON array i zwraca je jako listy)
        prace_nazbierane_tuples = [
            tuple(p) if isinstance(p, list) else p
            for p in (metryka.prace_nazbierane or [])
        ]

        # Debug dla Rogula
        from bpp.models import Autor

        try:
            autor = Autor.objects.get(pk=autor_id)
            if autor.nazwisko.startswith("Rogula"):
                logger.info(
                    f"DEBUG Rogula: autor_id={autor_id}, dyscyplina={dyscyplina_id_key}"
                )
                logger.info(
                    f"  prace_nazbierane raw (first 2): {metryka.prace_nazbierane[:2] if metryka.prace_nazbierane else []}"
                )
                logger.info(
                    f"  prace_nazbierane tuples (first 2): {prace_nazbierane_tuples[:2]}"
                )
                logger.info(
                    f"  total works in nazbierane: {len(prace_nazbierane_tuples)}"
                )
        except Autor.DoesNotExist:
            pass

        # Pobierz wszystkie prace dla tego autora i dyscypliny
        for cache_entry in Cache_Punktacja_Autora_Query.objects.filter(
            autor_id=autor_id, dyscyplina_id=dyscyplina_id_key
        ).select_related("rekord"):
            # Rekord.pk to tuple (content_type_id, object_id)
            rekord_tuple = cache_entry.rekord_id

            if rekord_tuple not in works_by_rekord:
                works_by_rekord[rekord_tuple] = {
                    "rekord": cache_entry.rekord,
                    "authors": [],
                }

            # Sprawdź czy ta praca weszła do zebranych tego autora
            praca_weszla = cache_entry.rekord_id in prace_nazbierane_tuples

            # Debug dla Rogula
            if autor.nazwisko.startswith("Rogula"):
                logger.info(
                    f"  Checking work {rekord_tuple}: praca_weszla={praca_weszla}, slot={cache_entry.slot}"
                )

            works_by_rekord[rekord_tuple]["authors"].append(
                {
                    "autor_id": autor_id,
                    "dyscyplina_id": dyscyplina_id_key,
                    "slot": cache_entry.slot,
                    "metryka": metryka,
                    "praca_weszla": praca_weszla,
                }
            )

    logger.info(f"Analyzing {len(works_by_rekord)} works with multiple authors")

    # Update progress
    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "unpinning",
            "step": "finding_opportunities",
            "progress": progress_offset + 50,
            "works_to_analyze": len(works_by_rekord),
        },
    )

    # Szukaj możliwości odpinania
    opportunities = []
    analyzed_count = 0

    # Cache dla metryk "przed odpięciem" - optymalizacja wydajności
    # Dla tej samej publikacji z wieloma kombinacjami A→B, metryki "przed" są identyczne
    # Klucz: publikacja.pk, wartość: results_before z przelicz_metryki_dla_publikacji()
    metrics_before_cache = {}

    for rekord_tuple, work_data in works_by_rekord.items():
        authors = work_data["authors"]

        # Pomiń prace z tylko jednym autorem
        if len(authors) < 2:
            continue

        rekord = work_data["rekord"]

        # Sprawdź pary autorów
        for autor_a in authors:
            # Autor A: praca NIE weszła
            if autor_a["praca_weszla"]:
                continue

            for autor_b in authors:
                # Autor B: praca WESZŁA
                if not autor_b["praca_weszla"]:
                    continue

                # Różni autorzy, ta sama dyscyplina
                if (
                    autor_a["autor_id"] == autor_b["autor_id"]
                    or autor_a["dyscyplina_id"] != autor_b["dyscyplina_id"]
                ):
                    continue

                # Sprawdź czy Autor B ma niepełne sloty (może wziąć więcej)
                slots_b_can_take = autor_b["metryka"].slot_niewykorzystany
                if slots_b_can_take <= 0:
                    # Autor B ma pełne sloty, nie ma sensu
                    continue

                # Sprawdź czy odpięcie ma sens przez symulację
                # slots_missing = ile Autor B może jeszcze wziąć
                # slot_in_work = slot Autora A w tej pracy
                slots_missing = slots_b_can_take
                slot_in_work = autor_a["slot"]

                # Symulacja odpięcia: sprawdź czy Autor B rzeczywiście zyskuje
                from bpp.models import (
                    Autor,
                    Dyscyplina_Naukowa,
                )

                try:
                    # Pobierz obiekty dla symulacji
                    autor_b_obj = Autor.objects.get(pk=autor_b["autor_id"])
                    dyscyplina_obj = Dyscyplina_Naukowa.objects.get(
                        pk=autor_a["dyscyplina_id"]
                    )

                    # Pobierz autor_assignment dla Autora A
                    publikacja_original = rekord.original

                    autor_assignment = publikacja_original.autorzy_set.filter(
                        autor_id=autor_a["autor_id"],
                        dyscyplina_naukowa=dyscyplina_obj,
                    ).first()

                    if autor_assignment is not None:
                        # Symuluj odpięcie (z cache dla optymalizacji)
                        simulation_result = simulate_unpinning_benefit(
                            autor_assignment,
                            autor_b_obj,
                            dyscyplina_obj,
                            metrics_before_cache=metrics_before_cache,
                        )

                        if simulation_result:
                            makes_sense = simulation_result["makes_sense"]
                            punkty_roznica_a = simulation_result["punkty_roznica_a"]
                            sloty_roznica_a = simulation_result["sloty_roznica_a"]
                            punkty_roznica_b = simulation_result["punkty_roznica_b"]
                            sloty_roznica_b = simulation_result["sloty_roznica_b"]
                        else:
                            # Symulacja się nie powiodła - fallback
                            makes_sense = False
                            punkty_roznica_a = Decimal("0")
                            sloty_roznica_a = Decimal("0")
                            punkty_roznica_b = Decimal("0")
                            sloty_roznica_b = Decimal("0")
                    else:
                        # Nie znaleziono autor_assignment - fallback do starej logiki
                        logger.warning(
                            f"Nie znaleziono autor_assignment dla autora {autor_a['autor_id']}, "
                            f"rekord {rekord_tuple}, dyscyplina {dyscyplina_obj}"
                        )
                        makes_sense = False
                        punkty_roznica_a = Decimal("0")
                        sloty_roznica_a = Decimal("0")
                        punkty_roznica_b = Decimal("0")
                        sloty_roznica_b = Decimal("0")

                except Exception as e:
                    # W przypadku błędu, fallback
                    logger.error(
                        f"Błąd podczas symulacji dla rekord {rekord_tuple}: {e}",
                        exc_info=True,
                    )
                    makes_sense = False
                    punkty_roznica_a = Decimal("0")
                    sloty_roznica_a = Decimal("0")
                    punkty_roznica_b = Decimal("0")
                    sloty_roznica_b = Decimal("0")

                opportunities.append(
                    {
                        "rekord_id": rekord_tuple,
                        "rekord_tytul": rekord.original.tytul_oryginalny[:500],
                        "autor_a": autor_a,
                        "autor_b": autor_b,
                        "slots_missing": slots_missing,
                        "slot_in_work": slot_in_work,
                        "makes_sense": makes_sense,
                        "punkty_roznica_a": punkty_roznica_a,
                        "sloty_roznica_a": sloty_roznica_a,
                        "punkty_roznica_b": punkty_roznica_b,
                        "sloty_roznica_b": sloty_roznica_b,
                    }
                )

        analyzed_count += 1
        if analyzed_count % 5 == 0:
            # Progress range: 60%-95% (offset+10 to offset+45)
            progress = (
                progress_offset + 10 + int((analyzed_count / len(works_by_rekord)) * 35)
            )
            task.update_state(
                state="PROGRESS",
                meta={
                    "stage": "unpinning",
                    "step": "finding_opportunities",
                    "progress": progress,
                    "analyzed": analyzed_count,
                    "total": len(works_by_rekord),
                    "found": len(opportunities),
                },
            )

    logger.info(f"Found {len(opportunities)} unpinning opportunities")

    # Update progress
    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "unpinning",
            "step": "saving_results",
            "progress": progress_offset + 45,  # 95% of total (90% of stage 2)
            "opportunities_found": len(opportunities),
        },
    )

    # Zapisz wyniki do bazy
    unpinning_objs = []
    for opp in opportunities:
        unpinning_objs.append(
            UnpinningOpportunity(
                uczelnia=uczelnia,
                dyscyplina_naukowa_id=opp["autor_a"]["dyscyplina_id"],
                rekord_id=opp["rekord_id"],
                rekord_tytul=opp["rekord_tytul"],
                autor_could_benefit_id=opp["autor_a"]["autor_id"],
                metryka_could_benefit=opp["autor_a"]["metryka"],
                slot_in_work=opp["slot_in_work"],
                slots_missing=opp["slots_missing"],
                autor_currently_using_id=opp["autor_b"]["autor_id"],
                metryka_currently_using=opp["autor_b"]["metryka"],
                makes_sense=opp["makes_sense"],
                punkty_roznica_a=opp["punkty_roznica_a"],
                sloty_roznica_a=opp["sloty_roznica_a"],
                punkty_roznica_b=opp["punkty_roznica_b"],
                sloty_roznica_b=opp["sloty_roznica_b"],
            )
        )

    # Bulk create w batch'ach
    batch_size = 500
    for i in range(0, len(unpinning_objs), batch_size):
        UnpinningOpportunity.objects.bulk_create(unpinning_objs[i : i + batch_size])

    logger.info(f"Saved {len(unpinning_objs)} unpinning opportunities to database")

    # Count by makes_sense
    sensible_count = sum(1 for opp in opportunities if opp["makes_sense"])

    result = {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "dyscyplina_id": dyscyplina_id,
        "total_opportunities": len(opportunities),
        "sensible_opportunities": sensible_count,
        "completed_at": datetime.now().isoformat(),
    }

    return result


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
    self, uczelnia_id, dyscyplina_id=None, min_slot_filled=0.8
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

    Returns:
        Dictionary z wynikami analizy
    """
    return _analyze_multi_author_works_impl(
        self, uczelnia_id, dyscyplina_id, min_slot_filled, progress_offset=0
    )


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id"],
    lock_expiry=10800,
    bind=True,
    time_limit=7200,
)
def unpin_all_sensible_task(self, uczelnia_id, min_slot_filled=0.8):  # noqa: C901
    """
    Odpina wszystkie sensowne możliwości odpinania (makes_sense=True),
    czeka na denormalizację i przelicza metryki + analizę unpinning.

    Args:
        uczelnia_id: ID uczelni dla której wykonać odpinanie
        min_slot_filled: Minimalny próg wypełnienia slotów dla ponownej analizy (domyślnie 0.8 = 80%)

    Returns:
        Dictionary z informacją o wykonanych operacjach
    """
    from celery import chain
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction

    from bpp.models import (
        Patent,
        Patent_Autor,
        Uczelnia,
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte,
        Wydawnictwo_Zwarte_Autor,
    )
    from ewaluacja_metryki.tasks import generuj_metryki_task_parallel
    from ewaluacja_metryki.utils import get_default_rodzaje_autora
    from snapshot_odpiec.models import SnapshotOdpiec

    from .models import UnpinningOpportunity

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(f"Starting unpin_all_sensible_task for {uczelnia}")

    # Update task state
    self.update_state(state="PROGRESS", meta={"step": "collecting", "progress": 5})

    # Get content types
    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)
    ct_patent = ContentType.objects.get_for_model(Patent)

    # Query all sensible unpinning opportunities for this uczelnia
    opportunities = UnpinningOpportunity.objects.filter(
        uczelnia=uczelnia, makes_sense=True
    ).select_related("autor_could_benefit", "dyscyplina_naukowa")

    total_opportunities = opportunities.count()

    logger.info(f"Found {total_opportunities} sensible unpinning opportunities")

    if total_opportunities == 0:
        logger.info("No sensible opportunities found, task completed")
        return {
            "uczelnia_id": uczelnia_id,
            "uczelnia_nazwa": str(uczelnia),
            "total_opportunities": 0,
            "unpinned_count": 0,
            "message": "Brak sensownych możliwości odpinania",
            "completed_at": datetime.now().isoformat(),
        }

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "snapshot",
            "progress": 10,
            "total_opportunities": total_opportunities,
        },
    )

    with transaction.atomic():
        # Create snapshot before unpinning
        snapshot = SnapshotOdpiec.objects.create(
            owner=None,  # System tworzy snapshot
            comment=f"przed odpięciem wszystkich sensownych możliwości - uczelnia {uczelnia}",
        )

        logger.info(
            f"Created snapshot {snapshot.pk} before unpinning all sensible opportunities "
            f"(uczelnia: {uczelnia})"
        )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "unpinning",
            "progress": 20,
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
        },
    )

    # Unpin all sensible opportunities
    unpinned_count = 0
    unpinned_ciagle = 0
    unpinned_zwarte = 0
    unpinned_patent = 0

    for idx, opportunity in enumerate(opportunities, 1):
        try:
            content_type_id = opportunity.rekord_id[0]
            object_id = opportunity.rekord_id[1]
            autor = opportunity.autor_could_benefit
            dyscyplina = opportunity.dyscyplina_naukowa

            # Determine which model to use based on content_type_id
            if content_type_id == ct_ciagle.pk:
                # Wydawnictwo_Ciagle_Autor
                updated = Wydawnictwo_Ciagle_Autor.objects.filter(
                    rekord_id=object_id, autor=autor, dyscyplina_naukowa=dyscyplina
                ).update(przypieta=False)
                unpinned_ciagle += updated
            elif content_type_id == ct_zwarte.pk:
                # Wydawnictwo_Zwarte_Autor
                updated = Wydawnictwo_Zwarte_Autor.objects.filter(
                    rekord_id=object_id, autor=autor, dyscyplina_naukowa=dyscyplina
                ).update(przypieta=False)
                unpinned_zwarte += updated
            elif content_type_id == ct_patent.pk:
                # Patent_Autor
                updated = Patent_Autor.objects.filter(
                    rekord_id=object_id, autor=autor, dyscyplina_naukowa=dyscyplina
                ).update(przypieta=False)
                unpinned_patent += updated
            else:
                logger.warning(
                    f"Unknown content_type_id {content_type_id} for opportunity {opportunity.pk}"
                )
                continue

            unpinned_count += updated

            if idx % 10 == 0:
                # Update progress every 10 opportunities
                progress = 20 + (idx / total_opportunities) * 30
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "step": "unpinning",
                        "progress": progress,
                        "snapshot_id": snapshot.pk,
                        "total_opportunities": total_opportunities,
                        "processed": idx,
                        "unpinned_count": unpinned_count,
                    },
                )

        except Exception as e:
            logger.error(
                f"Failed to unpin opportunity {opportunity.pk}: {e}", exc_info=True
            )

    logger.info(
        f"Unpinning complete. Total unpinned: {unpinned_count} "
        f"(Ciągłe: {unpinned_ciagle}, Zwarte: {unpinned_zwarte}, Patent: {unpinned_patent})"
    )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "waiting_denorm",
            "progress": 50,
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
            "unpinned_count": unpinned_count,
            "unpinned_ciagle": unpinned_ciagle,
            "unpinned_zwarte": unpinned_zwarte,
            "unpinned_patent": unpinned_patent,
        },
    )

    # Wait for denormalization
    logger.info("Waiting for denormalization...")
    _wait_for_denorm(
        self,
        progress_start=50,
        progress_range=20,
        meta_extra={
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
            "unpinned_count": unpinned_count,
            "unpinned_ciagle": unpinned_ciagle,
            "unpinned_zwarte": unpinned_zwarte,
            "unpinned_patent": unpinned_patent,
        },
        logger_func=logger.info,
    )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "recalculating_metrics",
            "progress": 70,
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
            "unpinned_count": unpinned_count,
            "message": "Uruchamianie przeliczania metryk...",
        },
    )

    # Chain: metrics recalculation -> unpinning analysis
    logger.info("Starting metrics recalculation and unpinning analysis")

    workflow = chain(
        generuj_metryki_task_parallel.s(
            rodzaje_autora=get_default_rodzaje_autora(),
            nadpisz=True,
            przelicz_liczbe_n=True,
        ),
        run_unpinning_after_metrics_wrapper.s(
            uczelnia_id=uczelnia.pk, dyscyplina_id=None, min_slot_filled=min_slot_filled
        ),
    )

    workflow_result = workflow.apply_async()

    logger.info(
        f"Metrics + unpinning analysis workflow started with task_id: {workflow_result.id}"
    )

    # Wait for workflow to complete with progress updates
    from time import sleep

    max_wait = 1800  # Max 30 minutes
    waited = 0
    check_interval = 10  # Check every 10 seconds

    while not workflow_result.ready() and waited < max_wait:
        sleep(check_interval)
        waited += check_interval

        # Calculate progress: 70-95% for this phase
        progress = min(70 + (waited / max_wait * 25), 95)

        # Try to get info about current workflow step
        # workflow_result.id is the ID of the LAST task in the chain (unpinning analysis)
        current_info = workflow_result.info if workflow_result.info else {}

        # Determine which phase we're in based on task info
        if isinstance(current_info, dict):
            current_step = current_info.get("step", "workflow_running")
        else:
            current_step = "workflow_running"

        self.update_state(
            state="PROGRESS",
            meta={
                "step": "workflow_running",
                "substep": current_step,
                "progress": progress,
                "snapshot_id": snapshot.pk,
                "total_opportunities": total_opportunities,
                "unpinned_count": unpinned_count,
                "message": "Przeliczanie metryk i analizy unpinning w trakcie...",
                "waited_seconds": waited,
            },
        )

        logger.info(
            f"Waiting for workflow completion... {waited}s elapsed, progress: {progress:.1f}%"
        )

    # Check if workflow completed successfully
    if workflow_result.ready():
        if workflow_result.successful():
            workflow_final_result = workflow_result.result
            logger.info(f"Workflow completed successfully: {workflow_final_result}")

            # Update to 100%
            self.update_state(
                state="PROGRESS",
                meta={
                    "step": "completed",
                    "progress": 100,
                    "snapshot_id": snapshot.pk,
                    "total_opportunities": total_opportunities,
                    "unpinned_count": unpinned_count,
                    "message": "Proces zakończony pomyślnie!",
                },
            )
        else:
            # Workflow failed
            error_info = str(workflow_result.info)
            logger.error(f"Workflow failed: {error_info}")
            raise Exception(
                f"Workflow przeliczania metryk i analizy nie powiódł się: {error_info}"
            )
    else:
        # Timeout
        logger.warning(f"Workflow timeout after {waited}s")
        raise Exception(
            f"Timeout: Workflow przeliczania metryk i analizy nie zakończył się w ciągu {max_wait}s"
        )

    result = {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "snapshot_id": snapshot.pk,
        "total_opportunities": total_opportunities,
        "unpinned_count": unpinned_count,
        "unpinned_ciagle": unpinned_ciagle,
        "unpinned_zwarte": unpinned_zwarte,
        "unpinned_patent": unpinned_patent,
        "workflow_task_id": workflow_result.id,
        "workflow_result": workflow_final_result,
        "completed_at": datetime.now().isoformat(),
    }

    logger.info(f"unpin_all_sensible_task completed: {result}")

    return result
