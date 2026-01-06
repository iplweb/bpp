"""Celery worker taski do równoległego przetwarzania analizy zamiany dyscyplin."""

import logging
from datetime import datetime
from decimal import Decimal

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, time_limit=1800)
def analyze_discipline_swap_worker_task(  # noqa: C901
    self,
    uczelnia_id,
    pub_rekord_ids,
    pubs_data,
    autor_dyscyplina_data,
    worker_id=0,
    total_workers=1,
):
    """
    Przetwarza podzbiór publikacji przypisanych do tego workera.

    Args:
        uczelnia_id: ID uczelni
        pub_rekord_ids: Lista [ct_id, pk] publikacji do przetworzenia
        pubs_data: Dane publikacji (serializowane) - dict z kluczami "ct_pk"
        autor_dyscyplina_data: Dane Autor_Dyscyplina (serializowane)
        worker_id: ID tego workera (0-based)
        total_workers: Całkowita liczba workerów

    Returns:
        dict: {"worker_id": int, "opportunities": list, "analyzed_count": int}
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models import Dyscyplina_Naukowa
    from bpp.models.zrodlo import Dyscyplina_Zrodla

    from .simulation import simulate_discipline_swap

    logger.info(
        f"Worker {worker_id}/{total_workers} starting: "
        f"{len(pub_rekord_ids)} publications to analyze"
    )

    opportunities = []
    analyzed_count = 0
    analysis_start_time = datetime.now()

    for rekord_id in pub_rekord_ids:
        ct_id, pub_pk = rekord_id[0], rekord_id[1]
        key = f"{ct_id}_{pub_pk}"

        pub_data = pubs_data.get(key)
        if not pub_data:
            continue

        authors = pub_data.get("authors", [])
        if len(authors) < 2:
            continue

        rok = pub_data.get("rok")
        pub_type = pub_data.get("pub_type")
        zrodlo_id = pub_data.get("zrodlo_id")

        # Pobierz publikację z bazy
        try:
            ct = ContentType.objects.get_for_id(ct_id)
            publikacja = ct.get_object_for_this_type(pk=pub_pk)
        except Exception as e:
            logger.error(f"Worker {worker_id}: Cannot get publication {key}: {e}")
            continue

        for author_info in authors:
            autor_id = author_info["autor_id"]
            dyscyplina_id = author_info["dyscyplina_id"]

            # Sprawdź Autor_Dyscyplina
            ad_key = f"{autor_id}_{rok}"
            ad_info = autor_dyscyplina_data.get(ad_key)

            if not ad_info:
                continue

            # Sprawdź czy autor ma dwie dyscypliny
            if not ad_info.get("subdyscyplina_id"):
                continue

            # Określ docelową dyscyplinę
            if dyscyplina_id == ad_info["dyscyplina_id"]:
                target_id = ad_info["subdyscyplina_id"]
            else:
                target_id = ad_info["dyscyplina_id"]

            if not target_id:
                continue

            # Pobierz obiekty z bazy
            try:
                autor_assignment = publikacja.autorzy_set.filter(
                    autor_id=autor_id,
                    dyscyplina_naukowa_id=dyscyplina_id,
                ).first()

                if not autor_assignment:
                    continue

                target_disc = Dyscyplina_Naukowa.objects.get(pk=target_id)
                current_disc = autor_assignment.dyscyplina_naukowa

            except Exception as e:
                logger.error(
                    f"Worker {worker_id}: Error getting objects for {key}: {e}"
                )
                continue

            # Symuluj zamianę
            result = simulate_discipline_swap(autor_assignment, target_disc)

            if result is None:
                continue

            # Sprawdź zgodność ze źródłem (tylko dla Wydawnictwo_Ciagle)
            zrodlo_match = False
            if pub_type == "Ciagle" and zrodlo_id:
                zrodlo_match = Dyscyplina_Zrodla.objects.filter(
                    zrodlo_id=zrodlo_id,
                    rok=rok,
                    dyscyplina_id=target_id,
                ).exists()

            # Serializuj wynik (Decimal -> str dla JSON)
            opportunities.append(
                {
                    "rekord_id": rekord_id,
                    "rekord_tytul": pub_data.get("rekord_tytul", "")[:500],
                    "rekord_rok": rok,
                    "rekord_typ": pub_type,
                    "autor_id": autor_id,
                    "current_discipline_id": current_disc.pk,
                    "target_discipline_id": target_id,
                    "points_before": str(result["points_before"]),
                    "points_after": str(result["points_after"]),
                    "point_improvement": str(result["point_improvement"]),
                    "zrodlo_discipline_match": zrodlo_match,
                    "makes_sense": result["makes_sense"],
                }
            )

        analyzed_count += 1

        # Aktualizuj postęp co 10 publikacji
        if analyzed_count % 10 == 0:
            elapsed_seconds = (datetime.now() - analysis_start_time).total_seconds()
            items_per_second = (
                analyzed_count / elapsed_seconds if elapsed_seconds > 0 else 0
            )
            self.update_state(
                state="PROGRESS",
                meta={
                    "worker_id": worker_id,
                    "analyzed": analyzed_count,
                    "total": len(pub_rekord_ids),
                    "found": len(opportunities),
                    "items_per_second": round(items_per_second, 2),
                },
            )

    logger.info(
        f"Worker {worker_id}/{total_workers} finished: "
        f"{len(opportunities)} opportunities found in {analyzed_count} publications"
    )

    return {
        "worker_id": worker_id,
        "opportunities": opportunities,
        "analyzed_count": analyzed_count,
    }


@shared_task(bind=True)
def collect_discipline_swap_results(self, worker_results, uczelnia_id):
    """
    Zbiera wyniki ze wszystkich workerów i zapisuje do bazy.

    Args:
        worker_results: Lista wyników z analyze_discipline_swap_worker_task
        uczelnia_id: ID uczelni

    Returns:
        dict: Podsumowanie wyników
    """
    from bpp.models import Autor, Dyscyplina_Naukowa, Uczelnia

    from ...models import DisciplineSwapOpportunity, StatusDisciplineSwapAnalysis

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(f"Collecting results from {len(worker_results)} workers for {uczelnia}")

    # Usuń stare wyniki
    DisciplineSwapOpportunity.objects.filter(uczelnia=uczelnia).delete()

    # Zbierz wszystkie opportunities
    all_opportunities = []
    total_analyzed = 0

    for result in worker_results:
        if result and "opportunities" in result:
            all_opportunities.extend(result["opportunities"])
            total_analyzed += result.get("analyzed_count", 0)

    logger.info(
        f"Collected {len(all_opportunities)} opportunities "
        f"from {total_analyzed} publications"
    )

    # Cache dla obiektów
    autor_cache = {}
    dyscyplina_cache = {}

    def get_autor(autor_id):
        if autor_id not in autor_cache:
            autor_cache[autor_id] = Autor.objects.get(pk=autor_id)
        return autor_cache[autor_id]

    def get_dyscyplina(dyscyplina_id):
        if dyscyplina_id not in dyscyplina_cache:
            dyscyplina_cache[dyscyplina_id] = Dyscyplina_Naukowa.objects.get(
                pk=dyscyplina_id
            )
        return dyscyplina_cache[dyscyplina_id]

    # Konwertuj opportunities na obiekty ORM
    objs = []
    for opp in all_opportunities:
        try:
            objs.append(
                DisciplineSwapOpportunity(
                    uczelnia=uczelnia,
                    rekord_id=tuple(opp["rekord_id"]),
                    rekord_tytul=opp["rekord_tytul"],
                    rekord_rok=opp["rekord_rok"],
                    rekord_typ=opp["rekord_typ"],
                    autor=get_autor(opp["autor_id"]),
                    current_discipline=get_dyscyplina(opp["current_discipline_id"]),
                    target_discipline=get_dyscyplina(opp["target_discipline_id"]),
                    points_before=Decimal(opp["points_before"]),
                    points_after=Decimal(opp["points_after"]),
                    point_improvement=Decimal(opp["point_improvement"]),
                    zrodlo_discipline_match=opp["zrodlo_discipline_match"],
                    makes_sense=opp["makes_sense"],
                )
            )
        except Exception as e:
            logger.error(f"Error creating opportunity object: {e}")
            continue

    # Zapisz do bazy w partiach
    batch_size = 500
    for i in range(0, len(objs), batch_size):
        DisciplineSwapOpportunity.objects.bulk_create(objs[i : i + batch_size])

    logger.info(f"Saved {len(objs)} discipline swap opportunities to database")

    sensible_count = sum(1 for opp in all_opportunities if opp["makes_sense"])

    # Aktualizuj status
    status = StatusDisciplineSwapAnalysis.get_or_create()
    status.zakoncz(f"Znaleziono {len(objs)} możliwości, {sensible_count} sensownych")

    return {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "total_opportunities": len(objs),
        "sensible_opportunities": sensible_count,
        "total_analyzed": total_analyzed,
        "workers_count": len(worker_results),
        "completed_at": datetime.now().isoformat(),
    }
