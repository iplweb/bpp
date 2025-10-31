import logging
import traceback
from datetime import datetime
from decimal import Decimal

from celery import group, shared_task
from celery_singleton import Singleton

from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from ewaluacja_optymalizacja.core import solve_discipline

logger = logging.getLogger(__name__)


@shared_task
def solve_single_discipline_task(uczelnia_id, dyscyplina_id, liczba_n):
    """
    Uruchamia optymalizację dla pojedynczej dyscypliny.

    To zadanie jest wywoływane równolegle dla każdej dyscypliny przez solve_all_reported_disciplines.

    Args:
        uczelnia_id: ID uczelni
        dyscyplina_id: ID dyscypliny naukowej
        liczba_n: wartość liczby N dla tej dyscypliny

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
            dyscyplina_nazwa=dyscyplina_nazwa, verbose=False, log_callback=None
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
def solve_all_reported_disciplines(self, uczelnia_id):
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
            uczelnia_id, dyscyplina.pk, float(liczba_n_obj.liczba_n)
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


def _should_unpin_publication(autor_id, rekord_id, logger_func):
    """Check if a publication should be unpinned based on slot value."""
    from decimal import Decimal

    from bpp.models import Cache_Punktacja_Autora_Query

    try:
        cache_entry = Cache_Punktacja_Autora_Query.objects.filter(
            autor_id=autor_id,
            rekord_id=list(rekord_id),
            dyscyplina__isnull=False,
        ).first()

        if cache_entry and cache_entry.slot < Decimal("1.0"):
            return True
        elif cache_entry is None:
            return True
        return False

    except Exception as e:
        logger_func(
            f"Error checking slot for autor {autor_id}, rekord {rekord_id}: {e}"
        )
        return True  # Unpin for safety


def _collect_ids_to_unpin(uczelnia, autorzy_z_wynikami, logger_func):
    """Collect IDs of publications to unpin."""
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
        # Collect all works shown for this author (from all disciplines)
        autor_wykazane_prace = set(
            OptimizationPublication.objects.filter(
                author_result__autor_id=autor_id,
                author_result__optimization_run__uczelnia=uczelnia,
                author_result__optimization_run__status="completed",
            ).values_list("rekord_id", flat=True)
        )

        # Wydawnictwa ciągłe
        for udział in Wydawnictwo_Ciagle_Autor.objects.filter(
            autor_id=autor_id, przypieta=True
        ).select_related("rekord"):
            rekord_id = (ct_ciagle.pk, udział.rekord.pk)

            if rekord_id not in autor_wykazane_prace and _should_unpin_publication(
                autor_id, rekord_id, logger_func
            ):
                ids_to_unpin_ciagle.append(udział.pk)

        # Wydawnictwa zwarte
        for udział in Wydawnictwo_Zwarte_Autor.objects.filter(
            autor_id=autor_id, przypieta=True
        ).select_related("rekord"):
            rekord_id = (ct_zwarte.pk, udział.rekord.pk)

            if rekord_id not in autor_wykazane_prace and _should_unpin_publication(
                autor_id, rekord_id, logger_func
            ):
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
    task, uczelnia, dyscypliny_ids, discipline_count, meta_extra, logger_func
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
            uczelnia.pk, dyscyplina.pk, float(liczba_n_obj.liczba_n)
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
def optimize_and_unpin_task(self, uczelnia_id):
    """
    Zadanie które:
    1. Sprawdza czy wszystkie dyscypliny raportowane są przeliczone
    2. Tworzy snapshot obecnego stanu przypięć
    3. Odpina dyscypliny w pracach niewykazanych do ewaluacji
    4. Automatycznie przelicza punktację całej uczelni

    Args:
        uczelnia_id: ID uczelni dla której wykonać optymalizację

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
def reset_all_pins_task(self, uczelnia_id):
    """
    Resetuje przypięcia dla wszystkich rekordów 2022-2025 gdzie autor ma dyscyplinę,
    jest zatrudniony i afiliuje.

    Args:
        uczelnia_id: ID uczelni dla której resetować przypięcia

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
