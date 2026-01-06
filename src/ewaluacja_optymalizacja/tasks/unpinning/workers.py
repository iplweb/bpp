"""Celery worker taski do równoległego przetwarzania unpinning."""

import logging
from datetime import datetime
from decimal import Decimal

from celery import shared_task

from .simulation import simulate_unpinning_benefit

logger = logging.getLogger(__name__)


@shared_task(bind=True, time_limit=1800)
def analyze_unpinning_worker_task(  # noqa: C901
    self,
    uczelnia_id,
    work_rekord_ids,
    works_data,
    metryki_data,
    dyscyplina_id=None,
    min_slot_filled=0.8,
    worker_id=0,
    total_workers=1,
):
    """
    Przetwarza podzbiór prac przypisanych do tego workera.

    Ten task jest wywoływany równolegle przez kilka workerów, każdy z innym
    podzbiorem prac. Gwarantujemy, że żaden autor nie jest współdzielony
    między workerami (dzięki klastrowaniu).

    Args:
        uczelnia_id: ID uczelni
        work_rekord_ids: Lista rekord_tuples do przetworzenia przez tego workera
        works_data: Dane prac (serializowane) - dict z kluczami jako stringami
        metryki_data: Dane metryk (serializowane) - dict z kluczami jako stringami
        dyscyplina_id: ID dyscypliny (opcjonalnie)
        min_slot_filled: Minimalny próg wypełnienia slotów
        worker_id: ID tego workera (0-based)
        total_workers: Całkowita liczba workerów

    Returns:
        list: Lista opportunities znalezionych przez tego workera (serializowane)
    """
    from bpp.models import Autor, Dyscyplina_Naukowa, Uczelnia

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(
        f"Worker {worker_id}/{total_workers} starting: "
        f"{len(work_rekord_ids)} works to analyze for {uczelnia}"
    )

    # Deserializuj works_data i metryki_data
    works_by_rekord = {}
    for _key_str, work_info in works_data.items():
        rekord_tuple = tuple(work_info["rekord_id"])
        works_by_rekord[rekord_tuple] = {
            "rekord_id": rekord_tuple,
            "rekord_tytul": work_info["rekord_tytul"],
            "authors": work_info["authors"],
        }

    metryki_dict = {}
    for key_str, metryka_info in metryki_data.items():
        key_parts = key_str.strip("()").split(", ")
        key = (int(key_parts[0]), int(key_parts[1]))
        metryki_dict[key] = metryka_info

    metrics_before_cache = {}

    opportunities = []
    analyzed_count = 0
    analysis_start_time = datetime.now()

    for rekord_tuple in work_rekord_ids:
        rekord_tuple = tuple(rekord_tuple)
        if rekord_tuple not in works_by_rekord:
            continue

        work_data = works_by_rekord[rekord_tuple]
        authors = work_data["authors"]

        if len(authors) < 2:
            continue

        # Pomijaj prace jednoautorskie - nie ma komu przekazać slotu
        distinct_author_ids = {a["autor_id"] for a in authors}
        if len(distinct_author_ids) < 2:
            continue

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

                metryka_b_key = (autor_b["autor_id"], autor_b["dyscyplina_id"])
                metryka_b_info = metryki_dict.get(metryka_b_key)
                if not metryka_b_info:
                    continue

                slots_b_can_take = Decimal(str(metryka_b_info["slot_niewykorzystany"]))
                if slots_b_can_take <= 0:
                    continue

                slots_missing = slots_b_can_take
                slot_in_work = Decimal(str(autor_a["slot"]))

                try:
                    autor_b_obj = Autor.objects.get(pk=autor_b["autor_id"])
                    dyscyplina_obj = Dyscyplina_Naukowa.objects.get(
                        pk=autor_a["dyscyplina_id"]
                    )

                    from django.contrib.contenttypes.models import ContentType

                    ct = ContentType.objects.get_for_id(rekord_tuple[0])
                    publikacja = ct.get_object_for_this_type(pk=rekord_tuple[1])

                    autor_assignment = publikacja.autorzy_set.filter(
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
                        makes_sense = False
                        punkty_roznica_a = Decimal("0")
                        sloty_roznica_a = Decimal("0")
                        punkty_roznica_b = Decimal("0")
                        sloty_roznica_b = Decimal("0")

                except Exception as e:
                    logger.error(
                        f"Worker {worker_id}: Error for rekord {rekord_tuple}: {e}",
                        exc_info=True,
                    )
                    makes_sense = False
                    punkty_roznica_a = Decimal("0")
                    sloty_roznica_a = Decimal("0")
                    punkty_roznica_b = Decimal("0")
                    sloty_roznica_b = Decimal("0")

                opportunities.append(
                    {
                        "rekord_id": list(rekord_tuple),
                        "rekord_tytul": work_data["rekord_tytul"],
                        "autor_a": autor_a,
                        "autor_b": autor_b,
                        "slots_missing": str(slots_missing),
                        "slot_in_work": str(slot_in_work),
                        "makes_sense": makes_sense,
                        "punkty_roznica_a": str(punkty_roznica_a),
                        "sloty_roznica_a": str(sloty_roznica_a),
                        "punkty_roznica_b": str(punkty_roznica_b),
                        "sloty_roznica_b": str(sloty_roznica_b),
                    }
                )

        analyzed_count += 1
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
                    "total": len(work_rekord_ids),
                    "found": len(opportunities),
                    "items_per_second": round(items_per_second, 2),
                },
            )

    logger.info(
        f"Worker {worker_id}/{total_workers} finished: "
        f"{len(opportunities)} opportunities found in {analyzed_count} works"
    )

    return {
        "worker_id": worker_id,
        "opportunities": opportunities,
        "analyzed_count": analyzed_count,
    }


@shared_task(bind=True)
def collect_unpinning_results(self, worker_results, uczelnia_id, dyscyplina_id=None):
    """
    Zbiera wyniki ze wszystkich workerów i zapisuje do bazy.

    Args:
        worker_results: Lista wyników z analyze_unpinning_worker_task
        uczelnia_id: ID uczelni
        dyscyplina_id: ID dyscypliny (opcjonalnie)

    Returns:
        dict: Podsumowanie wyników
    """
    from bpp.models import Uczelnia

    from ...models import UnpinningOpportunity

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(f"Collecting results from {len(worker_results)} workers for {uczelnia}")

    # Usuń stare wyniki
    if dyscyplina_id:
        UnpinningOpportunity.objects.filter(
            uczelnia=uczelnia, dyscyplina_naukowa_id=dyscyplina_id
        ).delete()
    else:
        UnpinningOpportunity.objects.filter(uczelnia=uczelnia).delete()

    # Zbierz wszystkie opportunities
    all_opportunities = []
    total_analyzed = 0

    for result in worker_results:
        if result and "opportunities" in result:
            all_opportunities.extend(result["opportunities"])
            total_analyzed += result.get("analyzed_count", 0)

    logger.info(
        f"Collected {len(all_opportunities)} opportunities from {total_analyzed} works"
    )

    # Zapisz do bazy
    unpinning_objs = []
    for opp in all_opportunities:
        from ewaluacja_metryki.models import MetrykaAutora

        metryka_a = MetrykaAutora.objects.filter(
            autor_id=opp["autor_a"]["autor_id"],
            dyscyplina_naukowa_id=opp["autor_a"]["dyscyplina_id"],
        ).first()
        metryka_b = MetrykaAutora.objects.filter(
            autor_id=opp["autor_b"]["autor_id"],
            dyscyplina_naukowa_id=opp["autor_b"]["dyscyplina_id"],
        ).first()

        if metryka_a and metryka_b:
            unpinning_objs.append(
                UnpinningOpportunity(
                    uczelnia=uczelnia,
                    dyscyplina_naukowa_id=opp["autor_a"]["dyscyplina_id"],
                    rekord_id=tuple(opp["rekord_id"]),
                    rekord_tytul=opp["rekord_tytul"][:500],
                    autor_could_benefit_id=opp["autor_a"]["autor_id"],
                    metryka_could_benefit=metryka_a,
                    slot_in_work=Decimal(opp["slot_in_work"]),
                    slots_missing=Decimal(opp["slots_missing"]),
                    autor_currently_using_id=opp["autor_b"]["autor_id"],
                    metryka_currently_using=metryka_b,
                    makes_sense=opp["makes_sense"],
                    punkty_roznica_a=Decimal(opp["punkty_roznica_a"]),
                    sloty_roznica_a=Decimal(opp["sloty_roznica_a"]),
                    punkty_roznica_b=Decimal(opp["punkty_roznica_b"]),
                    sloty_roznica_b=Decimal(opp["sloty_roznica_b"]),
                )
            )

    batch_size = 500
    for i in range(0, len(unpinning_objs), batch_size):
        UnpinningOpportunity.objects.bulk_create(unpinning_objs[i : i + batch_size])

    logger.info(f"Saved {len(unpinning_objs)} unpinning opportunities to database")

    sensible_count = sum(1 for opp in all_opportunities if opp["makes_sense"])

    return {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "dyscyplina_id": dyscyplina_id,
        "total_opportunities": len(all_opportunities),
        "sensible_opportunities": sensible_count,
        "total_analyzed": total_analyzed,
        "workers_count": len(worker_results),
        "completed_at": datetime.now().isoformat(),
    }
