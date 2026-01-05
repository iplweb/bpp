"""Główna implementacja analizy prac wieloautorskich dla unpinning."""

import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal

from celery import chord
from django.db.models import F

from .clustering import partition_works_into_chunks
from .simulation import simulate_unpinning_benefit

logger = logging.getLogger(__name__)


def _analyze_multi_author_works_impl(  # noqa: C901
    task,
    uczelnia_id,
    dyscyplina_id=None,
    min_slot_filled=0.8,
    progress_offset=0,
    parallel=True,
    num_workers=4,
):
    """
    Implementacja analizy prac wieloautorskich - wydzielona do wielokrotnego użycia.

    Args:
        task: Celery task object (self) do aktualizacji statusu
        uczelnia_id: ID uczelni
        dyscyplina_id: ID dyscypliny (opcjonalnie, jeśli None to wszystkie)
        min_slot_filled: Minimalny próg wypełnienia slotów (domyślnie 0.8 = 80%)
        progress_offset: Bazowy offset dla progressu (0-100)
        parallel: Czy używać równoległego przetwarzania (domyślnie True)
        num_workers: Liczba workerów dla przetwarzania równoległego (domyślnie 4)

    Returns:
        Dictionary z wynikami analizy
    """
    from bpp.models import Uczelnia
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora_Query
    from ewaluacja_metryki.models import MetrykaAutora

    from ...models import UnpinningOpportunity

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
            "progress": progress_offset + 5,
        },
    )

    # Filtruj metryki - szukamy autorów z PEŁNYMI slotami (>=80% wypełnienia)
    # Wykluczamy metryki gdzie slot_maksymalny = 0 (autor nie ma przypisanych slotów)
    metryki_qs = MetrykaAutora.objects.select_related(
        "autor", "dyscyplina_naukowa"
    ).filter(
        slot_maksymalny__gt=0,
        slot_nazbierany__gte=F("slot_maksymalny") * Decimal(str(min_slot_filled)),
    )

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
            "progress": progress_offset + 10,
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
                    f"  total works in nazbierane: {len(prace_nazbierane_tuples)}"
                )
        except Autor.DoesNotExist:
            pass

        # Pobierz wszystkie prace dla tego autora i dyscypliny
        for cache_entry in Cache_Punktacja_Autora_Query.objects.filter(
            autor_id=autor_id, dyscyplina_id=dyscyplina_id_key
        ).select_related("rekord"):
            rekord_tuple = cache_entry.rekord_id

            if rekord_tuple not in works_by_rekord:
                works_by_rekord[rekord_tuple] = {
                    "rekord": cache_entry.rekord,
                    "authors": [],
                }

            # Sprawdź czy ta praca weszła do zebranych tego autora
            praca_weszla = cache_entry.rekord_id in prace_nazbierane_tuples

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

    # =========================================================================
    # Tryb równoległy - podziel prace na chunki i uruchom workerów
    # =========================================================================
    if parallel and len(works_by_rekord) > 10:
        return _run_parallel_analysis(
            task=task,
            uczelnia=uczelnia,
            uczelnia_id=uczelnia_id,
            dyscyplina_id=dyscyplina_id,
            min_slot_filled=min_slot_filled,
            works_by_rekord=works_by_rekord,
            metryki_dict=metryki_dict,
            progress_offset=progress_offset,
        )

    # =========================================================================
    # Tryb sekwencyjny (fallback lub gdy parallel=False)
    # =========================================================================
    return _run_sequential_analysis(
        task=task,
        uczelnia=uczelnia,
        uczelnia_id=uczelnia_id,
        dyscyplina_id=dyscyplina_id,
        works_by_rekord=works_by_rekord,
        progress_offset=progress_offset,
    )


def _run_parallel_analysis(  # noqa: C901
    task,
    uczelnia,
    uczelnia_id,
    dyscyplina_id,
    min_slot_filled,
    works_by_rekord,
    metryki_dict,
    progress_offset,
):
    """Uruchamia równoległą analizę unpinning."""
    from time import sleep

    from celery import current_app

    from .workers import analyze_unpinning_worker_task, collect_unpinning_results

    chunk_size = 25  # ~25 prac na chunk - mniejsze chunki dla szybszego progressu
    chunks = partition_works_into_chunks(works_by_rekord, chunk_size=chunk_size)
    total_chunks = len(chunks)

    logger.info(
        f"Using parallel mode: {len(works_by_rekord)} works split into "
        f"{total_chunks} chunks of ~{chunk_size} works each"
    )

    # Serializuj dane dla workerów
    works_data = {}
    for rekord_tuple, work_data in works_by_rekord.items():
        key = str(rekord_tuple)
        works_data[key] = {
            "rekord_id": list(rekord_tuple),
            "rekord_tytul": (
                work_data["rekord"].original.tytul_oryginalny[:500]
                if hasattr(work_data["rekord"], "original")
                else str(work_data["rekord"])[:500]
            ),
            "authors": [
                {
                    "autor_id": a["autor_id"],
                    "dyscyplina_id": a["dyscyplina_id"],
                    "slot": str(a["slot"]),
                    "praca_weszla": a["praca_weszla"],
                }
                for a in work_data["authors"]
            ],
        }

    metryki_data = {}
    for (autor_id, dyscyplina_id_key), metryka in metryki_dict.items():
        key = str((autor_id, dyscyplina_id_key))
        metryki_data[key] = {
            "autor_id": autor_id,
            "dyscyplina_id": dyscyplina_id_key,
            "slot_niewykorzystany": str(metryka.slot_niewykorzystany),
            "slot_nazbierany": str(metryka.slot_nazbierany),
            "slot_maksymalny": str(metryka.slot_maksymalny),
        }

    # Utwórz taski dla każdego chunka
    worker_tasks = []
    for chunk_id, work_ids in enumerate(chunks):
        if work_ids:
            work_ids_serialized = [list(w) for w in work_ids]
            worker_tasks.append(
                analyze_unpinning_worker_task.s(
                    uczelnia_id=uczelnia_id,
                    work_rekord_ids=work_ids_serialized,
                    works_data=works_data,
                    metryki_data=metryki_data,
                    dyscyplina_id=dyscyplina_id,
                    min_slot_filled=min_slot_filled,
                    worker_id=chunk_id,
                    total_workers=total_chunks,
                )
            )

    if not worker_tasks:
        logger.warning("No chunk tasks created - falling back to sequential mode")
        return _run_sequential_analysis(
            task=task,
            uczelnia=uczelnia,
            uczelnia_id=uczelnia_id,
            dyscyplina_id=dyscyplina_id,
            works_by_rekord=works_by_rekord,
            progress_offset=progress_offset,
        )

    logger.info(f"Launching {len(worker_tasks)} chunk tasks")

    workflow = chord(worker_tasks)(
        collect_unpinning_results.s(
            uczelnia_id=uczelnia_id, dyscyplina_id=dyscyplina_id
        )
    )

    logger.info(f"Chord workflow created: id={workflow.id}")

    # Czekaj na zakończenie chord'a z aktualizacją postępu
    max_wait = 7200  # Max 2 godziny
    waited = 0
    check_interval = 2  # Sprawdzaj co 2 sekundy
    start_time = datetime.now()

    # Pobierz ID tasków workerów z chord'a
    # chord.parent zawiera GroupResult z taskami header
    worker_task_ids = []
    if hasattr(workflow, "parent") and workflow.parent:
        worker_task_ids = [t.id for t in workflow.parent.results]

    while not workflow.ready() and waited < max_wait:
        sleep(check_interval)
        waited += check_interval

        # Policz ukończone chunki sprawdzając status tasków
        completed_chunks = 0
        total_analyzed = 0
        total_found = 0

        if worker_task_ids:
            for task_id in worker_task_ids:
                try:
                    result = current_app.AsyncResult(task_id)
                    if result.ready():
                        completed_chunks += 1
                        if result.successful() and result.result:
                            total_analyzed += result.result.get("analyzed_count", 0)
                            total_found += len(result.result.get("opportunities", []))
                except Exception:
                    pass

        # Oblicz postęp na podstawie ukończonych chunków
        if total_chunks > 0:
            chunk_progress = completed_chunks / total_chunks
        else:
            chunk_progress = 0

        # Progress: scale from progress_offset to 99% (leaving 1% for finalization)
        available_range = 99 - progress_offset
        progress = progress_offset + int(available_range * chunk_progress)

        # Oblicz ETA
        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        if completed_chunks > 0 and chunk_progress > 0:
            estimated_total = elapsed_seconds / chunk_progress
            eta_seconds = estimated_total - elapsed_seconds
            # Add 10-20% random padding to ETA
            padding_factor = 1.0 + random.uniform(0.1, 0.2)
            padded_eta_seconds = int(eta_seconds * padding_factor)
            # Calculate actual finish time
            finish_time = datetime.now() + timedelta(seconds=padded_eta_seconds)
            eta_str = finish_time.strftime("%H:%M:%S")
        else:
            eta_str = "obliczanie..."

        task.update_state(
            state="PROGRESS",
            meta={
                "stage": "unpinning",
                "step": "parallel_chunks",
                "progress": progress,
                "chunks_total": total_chunks,
                "chunks_completed": completed_chunks,
                "works_count": len(works_by_rekord),
                "works_analyzed": total_analyzed,
                "opportunities_found": total_found,
                "eta": eta_str,
                "message": (
                    f"Przetwarzanie: {completed_chunks}/{total_chunks} porcji, "
                    f"ok. {eta_str}"
                ),
            },
        )

        if waited % 30 == 0:
            logger.info(
                f"Progress: {completed_chunks}/{total_chunks} porcji, zakończenie ~ {eta_str}"
            )

    # Sprawdź wynik
    if workflow.ready():
        if workflow.successful():
            chord_result = workflow.result
            logger.info(f"Parallel workflow completed: {chord_result}")

            return {
                "uczelnia_id": uczelnia_id,
                "uczelnia_nazwa": str(uczelnia),
                "dyscyplina_id": dyscyplina_id,
                "mode": "parallel",
                "chunks_count": total_chunks,
                "works_count": len(works_by_rekord),
                "chord_task_id": workflow.id,
                "chord_result": chord_result,
                "completed_at": datetime.now().isoformat(),
            }
        else:
            # Chord failed
            error_info = str(workflow.info)
            logger.error(f"Parallel workflow failed: {error_info}")
            raise Exception(f"Parallel unpinning workflow failed: {error_info}")
    else:
        # Timeout
        logger.warning(f"Parallel workflow timeout after {waited}s")
        raise Exception(
            f"Timeout: Parallel unpinning nie zakończył się w ciągu {max_wait}s"
        )


def _run_sequential_analysis(  # noqa: C901
    task,
    uczelnia,
    uczelnia_id,
    dyscyplina_id,
    works_by_rekord,
    progress_offset,
):
    """Uruchamia sekwencyjną analizę unpinning."""
    from ...models import UnpinningOpportunity

    logger.info("Using sequential mode for unpinning analysis")

    opportunities = []
    analyzed_count = 0
    analysis_start_time = datetime.now()
    metrics_before_cache = {}

    for rekord_tuple, work_data in works_by_rekord.items():
        authors = work_data["authors"]

        if len(authors) < 2:
            continue

        # Pomijaj prace jednoautorskie - nie ma komu przekazać slotu
        distinct_author_ids = {a["autor_id"] for a in authors}
        if len(distinct_author_ids) < 2:
            continue

        rekord = work_data["rekord"]

        for autor_a in authors:
            if autor_a["praca_weszla"]:
                continue

            for autor_b in authors:
                if not autor_b["praca_weszla"]:
                    continue

                if (
                    autor_a["autor_id"] == autor_b["autor_id"]
                    or autor_a["dyscyplina_id"] != autor_b["dyscyplina_id"]
                ):
                    continue

                slots_b_can_take = autor_b["metryka"].slot_niewykorzystany
                if slots_b_can_take <= 0:
                    continue

                slots_missing = slots_b_can_take
                slot_in_work = autor_a["slot"]

                from bpp.models import Autor, Dyscyplina_Naukowa

                try:
                    autor_b_obj = Autor.objects.get(pk=autor_b["autor_id"])
                    dyscyplina_obj = Dyscyplina_Naukowa.objects.get(
                        pk=autor_a["dyscyplina_id"]
                    )

                    publikacja_original = rekord.original

                    autor_assignment = publikacja_original.autorzy_set.filter(
                        autor_id=autor_a["autor_id"],
                        dyscyplina_naukowa=dyscyplina_obj,
                    ).first()

                    if autor_assignment is not None:
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
                            makes_sense = False
                            punkty_roznica_a = Decimal("0")
                            sloty_roznica_a = Decimal("0")
                            punkty_roznica_b = Decimal("0")
                            sloty_roznica_b = Decimal("0")
                    else:
                        logger.warning(
                            f"Nie znaleziono autor_assignment dla autora "
                            f"{autor_a['autor_id']}, rekord {rekord_tuple}"
                        )
                        makes_sense = False
                        punkty_roznica_a = Decimal("0")
                        sloty_roznica_a = Decimal("0")
                        punkty_roznica_b = Decimal("0")
                        sloty_roznica_b = Decimal("0")

                except Exception as e:
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
            progress = (
                progress_offset + 10 + int((analyzed_count / len(works_by_rekord)) * 35)
            )
            elapsed_seconds = (datetime.now() - analysis_start_time).total_seconds()
            items_per_second = (
                analyzed_count / elapsed_seconds if elapsed_seconds > 0 else 0
            )
            remaining_items = len(works_by_rekord) - analyzed_count
            estimated_seconds_remaining = (
                remaining_items / items_per_second if items_per_second > 0 else 0
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
                    "items_per_second": round(items_per_second, 2),
                    "estimated_seconds_remaining": int(estimated_seconds_remaining),
                },
            )

    logger.info(f"Found {len(opportunities)} unpinning opportunities")

    # Update progress
    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "unpinning",
            "step": "saving_results",
            "progress": progress_offset + 45,
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

    batch_size = 500
    for i in range(0, len(unpinning_objs), batch_size):
        UnpinningOpportunity.objects.bulk_create(unpinning_objs[i : i + batch_size])

    logger.info(f"Saved {len(unpinning_objs)} unpinning opportunities to database")

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
