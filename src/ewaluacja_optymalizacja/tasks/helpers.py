"""Funkcje pomocnicze dla tasków ewaluacja_optymalizacja."""

import logging

logger = logging.getLogger(__name__)


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

    from ..models import OptimizationRun

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
    from ewaluacja_metryki.models import MetrykaAutora

    from ..models import OptimizationPublication

    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    ids_to_unpin_ciagle = []
    ids_to_unpin_zwarte = []

    for autor_id in autorzy_z_wynikami:
        # Pobierz prace nazbierane dla tego autora (z wszystkich dyscyplin)
        # Te prace NIE powinny być odpinane, nawet jeśli mają slot < 1.0
        autor_prace_nazbierane = set()
        for metryka in MetrykaAutora.objects.filter(autor_id=autor_id):
            if metryka.prace_nazbierane:
                for praca_id in metryka.prace_nazbierane:
                    # JSONField może zwrócić list zamiast tuple - konwertuj
                    autor_prace_nazbierane.add(
                        tuple(praca_id) if isinstance(praca_id, list) else praca_id
                    )

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

            # Unpin if:
            # 1. NOT in prace_nazbierane (not collected for evaluation), AND
            # 2. slot < 1.0 (or not in optimization at all)
            slots = autor_wykazane_prace.get(rekord_id)
            if rekord_id not in autor_prace_nazbierane and (
                slots is None or slots < Decimal("1.0")
            ):
                ids_to_unpin_ciagle.append(udział.pk)

        # Wydawnictwa zwarte - only years 2022-2025
        for udział in Wydawnictwo_Zwarte_Autor.objects.filter(
            autor_id=autor_id,
            przypieta=True,
            rekord__rok__gte=2022,
            rekord__rok__lt=2026,
        ).select_related("rekord"):
            rekord_id = (ct_zwarte.pk, udział.rekord.pk)

            # Unpin if:
            # 1. NOT in prace_nazbierane (not collected for evaluation), AND
            # 2. slot < 1.0 (or not in optimization at all)
            slots = autor_wykazane_prace.get(rekord_id)
            if rekord_id not in autor_prace_nazbierane and (
                slots is None or slots < Decimal("1.0")
            ):
                ids_to_unpin_zwarte.append(udział.pk)

    logger_func(
        f"Prepared to unpin {len(ids_to_unpin_ciagle)} Wydawnictwo_Ciagle_Autor records "
        f"and {len(ids_to_unpin_zwarte)} Wydawnictwo_Zwarte_Autor records"
    )

    return ids_to_unpin_ciagle, ids_to_unpin_zwarte


def _update_with_retry(
    model, batch_ids, batch_num, total_batches, model_name, logger_func
):
    """Execute update with retry on deadlock."""
    from time import sleep

    from django.db import OperationalError, transaction

    max_retries = 3
    retry_delay = 2  # sekundy

    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                model.objects.filter(pk__in=batch_ids).update(przypieta=False)
            logger_func(f"Unpinned {model_name} batch {batch_num}/{total_batches}")
            return
        except OperationalError as e:
            error_msg = str(e).lower()
            is_deadlock = "deadlock" in error_msg or "zakleszczenie" in error_msg
            if is_deadlock and attempt < max_retries - 1:
                logger_func(
                    f"Deadlock detected in {model_name}, "
                    f"retry {attempt + 1}/{max_retries}"
                )
                sleep(retry_delay * (attempt + 1))  # exponential backoff
            else:
                raise


def _calculate_eta_seconds(start_time, batches_processed, total_batches_all):
    """Calculate ETA in seconds based on batch processing velocity."""
    import time

    elapsed_time = time.time() - start_time
    if elapsed_time > 2 and batches_processed > 0:
        batches_per_second = batches_processed / elapsed_time
        remaining_batches = total_batches_all - batches_processed
        if batches_per_second > 0:
            return int(remaining_batches / batches_per_second)
    return None


def _update_task_progress(
    task,
    batches_processed,
    total_batches_all,
    current_batch,
    total_batches,
    ids_unpinned_so_far,
    total_to_unpin,
    phase_name,
    phase_label,
    start_time,
):
    """Update Celery task progress during unpinning."""
    if not task:
        return

    progress = 20 + (batches_processed / total_batches_all) * 30
    task.update_state(
        state="PROGRESS",
        meta={
            "step": "unpinning",
            "progress": progress,
            "message": f"Odpinanie {phase_label}: porcja {current_batch}/{total_batches}",
            "unpinning_phase": phase_name,
            "current_batch": current_batch,
            "total_batches": total_batches,
            "unpinned_so_far": ids_unpinned_so_far,
            "total_to_unpin": total_to_unpin,
            "batches_processed_all": batches_processed,
            "total_batches_all": total_batches_all,
            "eta_seconds": _calculate_eta_seconds(
                start_time, batches_processed, total_batches_all
            ),
        },
    )


def _process_unpinning_batches(
    model,
    ids_to_unpin,
    model_name,
    phase_name,
    phase_label,
    batch_size,
    batches_processed,
    total_batches_all,
    start_time,
    task,
    logger_func,
):
    """Process unpinning batches for a single model type."""
    from time import sleep

    if not ids_to_unpin:
        return batches_processed

    total_batches = (len(ids_to_unpin) + batch_size - 1) // batch_size

    for i in range(0, len(ids_to_unpin), batch_size):
        batch_ids = ids_to_unpin[i : i + batch_size]
        current_batch = i // batch_size + 1
        _update_with_retry(
            model, batch_ids, current_batch, total_batches, model_name, logger_func
        )
        batches_processed += 1

        _update_task_progress(
            task,
            batches_processed,
            total_batches_all,
            current_batch,
            total_batches,
            min(i + batch_size, len(ids_to_unpin)),
            len(ids_to_unpin),
            phase_name,
            phase_label,
            start_time,
        )

        sleep(0.5)

    logger_func(f"Unpinned {len(ids_to_unpin)} {model_name} records")
    return batches_processed


def _perform_batch_unpinning(
    ids_to_unpin_ciagle, ids_to_unpin_zwarte, logger_func, task=None
):
    """Perform batch unpinning operations with deadlock retry and progress tracking."""
    import time

    from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

    batch_size = 50

    # Calculate total batches for progress tracking
    total_batches_ciagle = (
        (len(ids_to_unpin_ciagle) + batch_size - 1) // batch_size
        if ids_to_unpin_ciagle
        else 0
    )
    total_batches_zwarte = (
        (len(ids_to_unpin_zwarte) + batch_size - 1) // batch_size
        if ids_to_unpin_zwarte
        else 0
    )
    total_batches_all = total_batches_ciagle + total_batches_zwarte

    start_time = time.time()
    batches_processed = 0

    batches_processed = _process_unpinning_batches(
        Wydawnictwo_Ciagle_Autor,
        ids_to_unpin_ciagle,
        "Wydawnictwo_Ciagle_Autor",
        "ciagle",
        "wydawnictw ciągłych",
        batch_size,
        batches_processed,
        total_batches_all,
        start_time,
        task,
        logger_func,
    )

    batches_processed = _process_unpinning_batches(
        Wydawnictwo_Zwarte_Autor,
        ids_to_unpin_zwarte,
        "Wydawnictwo_Zwarte_Autor",
        "zwarte",
        "wydawnictw zwartych",
        batch_size,
        batches_processed,
        total_batches_all,
        start_time,
        task,
        logger_func,
    )

    return len(ids_to_unpin_ciagle), len(ids_to_unpin_zwarte)


def _wait_for_denorm(task, progress_start, progress_range, meta_extra, logger_func):
    """Wait for denormalization to complete."""
    from time import sleep

    from denorm.models import DirtyInstance

    # UWAGA: flush_via_queue.delay() wykomentowane aby uniknąć deadlocków
    # Denorm można uruchomić ręcznie później lub po zakończeniu całego procesu
    # from denorm.tasks import flush_via_queue
    # flush_via_queue.delay()
    logger_func("Skipped triggering denorm flush via queue (deadlock prevention)")

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
