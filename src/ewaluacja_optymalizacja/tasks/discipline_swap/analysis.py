"""Główna implementacja analizy możliwości zamiany dyscyplin."""

import logging
import random
from datetime import datetime, timedelta
from itertools import chain
from time import sleep

from .simulation import simulate_discipline_swap

logger = logging.getLogger(__name__)


def _serialize_publications(ciagle_qs, zwarte_qs):
    """
    Serializuje publikacje do formatu JSON-safe dla workerów.

    Args:
        ciagle_qs: QuerySet Wydawnictwo_Ciagle
        zwarte_qs: QuerySet Wydawnictwo_Zwarte

    Returns:
        tuple: (pubs_data dict, rekord_ids list)
    """
    from django.contrib.contenttypes.models import ContentType

    pubs_data = {}
    rekord_ids = []

    for pub in chain(ciagle_qs, zwarte_qs):
        ct = ContentType.objects.get_for_model(pub)
        rekord_id = [ct.pk, pub.pk]

        key = f"{ct.pk}_{pub.pk}"
        rekord_ids.append(rekord_id)

        # Pobierz autorów spełniających kryteria
        authors = [
            {
                "autor_id": a.autor_id,
                "dyscyplina_id": a.dyscyplina_naukowa_id,
            }
            for a in pub.autorzy_set.filter(
                afiliuje=True,
                zatrudniony=True,
                przypieta=True,
                dyscyplina_naukowa__isnull=False,
            )
        ]

        pubs_data[key] = {
            "rekord_id": rekord_id,
            "rekord_tytul": pub.tytul_oryginalny[:500] if pub.tytul_oryginalny else "",
            "rok": pub.rok,
            "pub_type": "Ciagle" if hasattr(pub, "zrodlo") else "Zwarte",
            "zrodlo_id": (
                getattr(pub.zrodlo, "pk", None)
                if hasattr(pub, "zrodlo") and pub.zrodlo
                else None
            ),
            "authors": authors,
        }

    return pubs_data, rekord_ids


def _serialize_autor_dyscyplina(rok_min, rok_max):
    """
    Serializuje Autor_Dyscyplina dla workerów.

    Args:
        rok_min: Minimalny rok
        rok_max: Maksymalny rok

    Returns:
        dict: Dane Autor_Dyscyplina z kluczami "autor_id_rok"
    """
    from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina

    ad_data = {}
    for ad in Autor_Dyscyplina.objects.filter(
        rok__gte=rok_min, rok__lte=rok_max
    ).values("autor_id", "rok", "dyscyplina_naukowa_id", "subdyscyplina_naukowa_id"):
        key = f"{ad['autor_id']}_{ad['rok']}"
        ad_data[key] = {
            "dyscyplina_id": ad["dyscyplina_naukowa_id"],
            "subdyscyplina_id": ad["subdyscyplina_naukowa_id"],
        }
    return ad_data


def partition_works_into_chunks(rekord_ids, chunk_size=50):
    """
    Dzieli publikacje na chunki o określonej wielkości.

    Args:
        rekord_ids: Lista [ct_id, pk] par
        chunk_size: Docelowa liczba publikacji w każdym chunku

    Returns:
        list: Lista chunków (każdy chunk to lista rekord_ids)
    """
    total = len(rekord_ids)
    if total == 0:
        return []

    num_chunks = max(1, (total + chunk_size - 1) // chunk_size)
    chunks = []
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min(start_idx + chunk_size, total)
        chunks.append(rekord_ids[start_idx:end_idx])
    return chunks


def _analyze_discipline_swap_impl(  # noqa: C901
    task,
    uczelnia_id,
    rok_min=2022,
    rok_max=2025,
):
    """
    Implementacja analizy możliwości zamiany dyscyplin.

    Algorytm:
    1. Pobierz publikacje z lat rok_min do rok_max
    2. Dla każdej publikacji z >= 2 autorami (afiliuje=True, zatrudniony=True):
       a) Sprawdź czy któryś autor ma dwie_dyscypliny() w Autor_Dyscyplina
       b) Symuluj zamianę dyscypliny (primary <-> sub)
       c) Oblicz punkty PRZED i PO zamianie
       d) Jeśli PO > PRZED, zapisz jako "sensowne"
       e) Dla Wydawnictwo_Ciagle sprawdź Dyscyplina_Zrodla

    Args:
        task: Celery task object (self) do aktualizacji statusu
        uczelnia_id: ID uczelni
        rok_min: Minimalny rok analizy (domyślnie 2022)
        rok_max: Maksymalny rok analizy (domyślnie 2025)

    Returns:
        Dictionary z wynikami analizy
    """
    from bpp.models import Uczelnia, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    from ...models import DisciplineSwapOpportunity

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(
        f"Starting discipline swap analysis for {uczelnia}, years {rok_min}-{rok_max}"
    )

    # Aktualizuj status
    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "starting",
            "progress": 0,
            "message": "Rozpoczynanie analizy...",
        },
    )

    # Usuń stare wyniki dla tej uczelni
    DisciplineSwapOpportunity.objects.filter(uczelnia=uczelnia).delete()

    # Pobierz publikacje z zakresu lat
    ciagle_qs = Wydawnictwo_Ciagle.objects.filter(
        rok__gte=rok_min, rok__lte=rok_max
    ).prefetch_related(
        "autorzy_set__autor",
        "autorzy_set__dyscyplina_naukowa",
    )

    zwarte_qs = Wydawnictwo_Zwarte.objects.filter(
        rok__gte=rok_min, rok__lte=rok_max
    ).prefetch_related(
        "autorzy_set__autor",
        "autorzy_set__dyscyplina_naukowa",
    )

    total_ciagle = ciagle_qs.count()
    total_zwarte = zwarte_qs.count()
    total_count = total_ciagle + total_zwarte

    logger.info(
        f"Found {total_ciagle} Wydawnictwo_Ciagle and {total_zwarte} "
        f"Wydawnictwo_Zwarte to analyze"
    )

    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "loading",
            "progress": 5,
            "total": total_count,
            "message": f"Znaleziono {total_count} publikacji do analizy",
        },
    )

    # Serializuj dane dla workerów
    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "serializing",
            "progress": 8,
            "message": "Przygotowywanie danych dla workerów...",
        },
    )

    logger.info("Serializing publications for parallel processing...")
    pubs_data, rekord_ids = _serialize_publications(ciagle_qs, zwarte_qs)

    logger.info("Serializing Autor_Dyscyplina data...")
    ad_data = _serialize_autor_dyscyplina(rok_min, rok_max)

    logger.info(
        f"Serialized {len(pubs_data)} publications and {len(ad_data)} "
        "Autor_Dyscyplina records"
    )

    # Uruchom analizę równoległą
    return _run_parallel_analysis(
        task=task,
        uczelnia=uczelnia,
        uczelnia_id=uczelnia_id,
        pubs_data=pubs_data,
        rekord_ids=rekord_ids,
        ad_data=ad_data,
        rok_min=rok_min,
        rok_max=rok_max,
    )


def _run_parallel_analysis(  # noqa: C901
    task,
    uczelnia,
    uczelnia_id,
    pubs_data,
    rekord_ids,
    ad_data,
    rok_min,
    rok_max,
):
    """
    Uruchamia równoległą analizę discipline swap.

    Używa Celery chord do równoległego przetwarzania publikacji
    przez wiele workerów.
    """
    from celery import chord, current_app

    from .workers import (
        analyze_discipline_swap_worker_task,
        collect_discipline_swap_results,
    )

    chunk_size = 50
    chunks = partition_works_into_chunks(rekord_ids, chunk_size=chunk_size)
    total_chunks = len(chunks)

    if total_chunks == 0:
        logger.warning("No publications to analyze")
        return {
            "uczelnia_id": uczelnia_id,
            "uczelnia_nazwa": str(uczelnia),
            "total_opportunities": 0,
            "sensible_opportunities": 0,
            "analyzed_publications": 0,
            "rok_min": rok_min,
            "rok_max": rok_max,
            "completed_at": datetime.now().isoformat(),
        }

    logger.info(
        f"Using parallel mode: {len(rekord_ids)} publications split into "
        f"{total_chunks} chunks of ~{chunk_size} publications each"
    )

    # Utwórz taski dla każdego chunka
    worker_tasks = []
    for chunk_id, pub_ids in enumerate(chunks):
        if pub_ids:
            worker_tasks.append(
                analyze_discipline_swap_worker_task.s(
                    uczelnia_id=uczelnia_id,
                    pub_rekord_ids=pub_ids,
                    pubs_data=pubs_data,
                    autor_dyscyplina_data=ad_data,
                    worker_id=chunk_id,
                    total_workers=total_chunks,
                )
            )

    if not worker_tasks:
        logger.warning("No worker tasks created")
        return {
            "uczelnia_id": uczelnia_id,
            "uczelnia_nazwa": str(uczelnia),
            "total_opportunities": 0,
            "sensible_opportunities": 0,
            "analyzed_publications": 0,
            "rok_min": rok_min,
            "rok_max": rok_max,
            "completed_at": datetime.now().isoformat(),
        }

    logger.info(f"Launching {len(worker_tasks)} chunk tasks")

    workflow = chord(worker_tasks)(
        collect_discipline_swap_results.s(uczelnia_id=uczelnia_id)
    )

    logger.info(f"Chord workflow created: id={workflow.id}")

    # Czekaj na zakończenie chord'a z aktualizacją postępu
    max_wait = 7200  # Max 2 godziny
    waited = 0
    check_interval = 2
    start_time = datetime.now()
    progress_offset = 10  # Zaczynamy od 10% (po serializacji)

    # Pobierz ID tasków workerów z chord'a
    worker_task_ids = []
    if hasattr(workflow, "parent") and workflow.parent:
        worker_task_ids = [t.id for t in workflow.parent.results]

    while not workflow.ready() and waited < max_wait:
        sleep(check_interval)
        waited += check_interval

        # Policz ukończone chunki
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

        # Oblicz postęp
        if total_chunks > 0:
            chunk_progress = completed_chunks / total_chunks
        else:
            chunk_progress = 0

        available_range = 90 - progress_offset
        progress = progress_offset + int(available_range * chunk_progress)

        # Oblicz ETA
        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        if completed_chunks > 0 and chunk_progress > 0:
            estimated_total = elapsed_seconds / chunk_progress
            eta_seconds = estimated_total - elapsed_seconds
            padding_factor = 1.0 + random.uniform(0.1, 0.2)
            padded_eta_seconds = int(eta_seconds * padding_factor)
            finish_time = datetime.now() + timedelta(seconds=padded_eta_seconds)
            eta_str = finish_time.strftime("%H:%M:%S")
        else:
            eta_str = "obliczanie..."

        task.update_state(
            state="PROGRESS",
            meta={
                "stage": "parallel_analysis",
                "progress": progress,
                "chunks_total": total_chunks,
                "chunks_completed": completed_chunks,
                "publications_count": len(rekord_ids),
                "publications_analyzed": total_analyzed,
                "opportunities_found": total_found,
                "eta": eta_str,
                "message": (
                    f"Przetwarzanie: {completed_chunks}/{total_chunks} porcji, "
                    f"znaleziono {total_found} możliwości, zakończenie ~ {eta_str}"
                ),
            },
        )

        if waited % 30 == 0:
            logger.info(
                f"Progress: {completed_chunks}/{total_chunks} chunks, ETA: {eta_str}"
            )

    # Sprawdź wynik
    if workflow.ready():
        if workflow.successful():
            chord_result = workflow.result
            logger.info(f"Parallel workflow completed: {chord_result}")

            return {
                "uczelnia_id": uczelnia_id,
                "uczelnia_nazwa": str(uczelnia),
                "mode": "parallel",
                "chunks_count": total_chunks,
                "publications_count": len(rekord_ids),
                "chord_task_id": workflow.id,
                "total_opportunities": chord_result.get("total_opportunities", 0),
                "sensible_opportunities": chord_result.get("sensible_opportunities", 0),
                "analyzed_publications": chord_result.get("total_analyzed", 0),
                "rok_min": rok_min,
                "rok_max": rok_max,
                "completed_at": datetime.now().isoformat(),
            }
        else:
            error_info = str(workflow.info)
            logger.error(f"Parallel workflow failed: {error_info}")
            raise Exception(f"Parallel discipline swap workflow failed: {error_info}")
    else:
        logger.warning(f"Parallel workflow timeout after {waited}s")
        raise Exception(
            f"Timeout: Parallel discipline swap nie zakończył się w ciągu {max_wait}s"
        )


def _analyze_single_publication(
    publikacja,
    pub_type,
    uczelnia,
    get_autor_dyscyplina,
    opportunities,
):
    """
    Analizuje pojedynczą publikację pod kątem możliwości zamiany dyscyplin.

    Args:
        publikacja: Obiekt Wydawnictwo_Ciagle lub Wydawnictwo_Zwarte
        pub_type: "Ciagle" lub "Zwarte"
        uczelnia: Obiekt Uczelnia
        get_autor_dyscyplina: Funkcja do pobierania Autor_Dyscyplina
        opportunities: Lista do której dodajemy znalezione możliwości
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models.zrodlo import Dyscyplina_Zrodla

    rok = publikacja.rok

    # Pobierz wszystkich autorów z afiliuje=True, zatrudniony=True, przypieta=True
    eligible_authors = list(
        publikacja.autorzy_set.filter(
            afiliuje=True,
            zatrudniony=True,
            dyscyplina_naukowa__isnull=False,
            przypieta=True,
        ).select_related("autor", "dyscyplina_naukowa")
    )

    # Musi być co najmniej 2 autorów
    if len(eligible_authors) < 2:
        return

    # Pobierz ContentType dla rekord_id
    ct = ContentType.objects.get_for_model(publikacja)

    # Sprawdź każdego autora
    for autor_assignment in eligible_authors:
        autor = autor_assignment.autor

        # Pobierz Autor_Dyscyplina dla tego roku
        autor_dyscyplina = get_autor_dyscyplina(autor.pk, rok)
        if autor_dyscyplina is None:
            continue

        # Sprawdź czy autor ma dwie dyscypliny
        if not autor_dyscyplina.dwie_dyscypliny():
            continue

        # Określ obecną i docelową dyscyplinę
        current_disc = autor_assignment.dyscyplina_naukowa

        if current_disc.pk == autor_dyscyplina.dyscyplina_naukowa_id:
            target_disc = autor_dyscyplina.subdyscyplina_naukowa
        else:
            target_disc = autor_dyscyplina.dyscyplina_naukowa

        if target_disc is None:
            continue

        # Symuluj zamianę
        result = simulate_discipline_swap(autor_assignment, target_disc)

        if result is None:
            continue

        # Sprawdź zgodność ze źródłem (tylko dla Wydawnictwo_Ciagle)
        zrodlo_match = False
        if pub_type == "Ciagle" and hasattr(publikacja, "zrodlo") and publikacja.zrodlo:
            zrodlo_match = Dyscyplina_Zrodla.objects.filter(
                zrodlo=publikacja.zrodlo,
                rok=rok,
                dyscyplina=target_disc,
            ).exists()

        opportunities.append(
            {
                "uczelnia": uczelnia,
                "rekord_id": (ct.pk, publikacja.pk),
                "rekord_tytul": publikacja.tytul_oryginalny[:500],
                "rekord_rok": rok,
                "rekord_typ": pub_type,
                "autor": autor,
                "current_discipline": current_disc,
                "target_discipline": target_disc,
                "points_before": result["points_before"],
                "points_after": result["points_after"],
                "point_improvement": result["point_improvement"],
                "zrodlo_discipline_match": zrodlo_match,
                "makes_sense": result["makes_sense"],
            }
        )


def _update_progress(task, analyzed, total, found, start_time):
    """Aktualizuje postęp zadania."""
    if total == 0:
        progress = 0
    else:
        progress = 5 + int((analyzed / total) * 85)

    elapsed = (datetime.now() - start_time).total_seconds()
    speed = analyzed / elapsed if elapsed > 0 else 0

    remaining = total - analyzed
    eta_seconds = remaining / speed if speed > 0 else 0

    task.update_state(
        state="PROGRESS",
        meta={
            "stage": "analyzing",
            "progress": progress,
            "analyzed": analyzed,
            "total": total,
            "found": found,
            "speed": round(speed, 2),
            "eta_seconds": int(eta_seconds),
            "message": f"Przeanalizowano {analyzed}/{total} publikacji, "
            f"znaleziono {found} możliwości",
        },
    )
