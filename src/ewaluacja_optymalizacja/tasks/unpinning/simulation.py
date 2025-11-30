"""Symulacja odpięcia pracy i obliczanie korzyści punktowych."""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def simulate_unpinning_benefit(  # noqa: C901
    autor_assignment,
    autor_currently_using,
    dyscyplina_naukowa,
    metrics_before_cache=None,
):
    """
    Symuluje odpięcie pracy dla jednego autora i sprawdza czy instytucja zyskuje punkty.

    Args:
        autor_assignment: Obiekt *_Autor (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor,
                         Patent_Autor) reprezentujący przypięcie do odpinania
        autor_currently_using: Obiekt Autor który obecnie ma pracę w zebranych
        dyscyplina_naukowa: Obiekt Dyscyplina_Naukowa
        metrics_before_cache: dict (optional) - cache dla metryk "przed odpięciem"
                             {publikacja.pk: results_before} używany do optymalizacji

    Returns:
        dict: {
            'makes_sense': bool - True jeśli odpięcie ma sens,
            'punkty_roznica_a': Decimal - różnica punktów dla autora A,
            'sloty_roznica_a': Decimal - różnica slotów dla autora A,
            'punkty_roznica_b': Decimal - różnica punktów dla autora B,
            'sloty_roznica_b': Decimal - różnica slotów dla autora B,
        }
        lub None jeśli nie udało się przeprowadzić symulacji
    """
    from django.db import transaction

    from bpp.models.sloty.core import IPunktacjaCacher
    from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

    try:
        # Cała symulacja w jednej transakcji
        with transaction.atomic():
            autor_a = autor_assignment.autor
            publikacja = autor_assignment.rekord

            # Symulacja w transakcji z savepoint
            sid = transaction.savepoint()

            try:
                # 1. Oblicz metryki PRZED odpięciem (z cache jeśli dostępny)
                publikacja_pk = publikacja.pk

                if (
                    metrics_before_cache is not None
                    and publikacja_pk in metrics_before_cache
                ):
                    results_before = metrics_before_cache[publikacja_pk]
                    logger.debug(
                        f"Cache HIT dla publikacji {publikacja.tytul_oryginalny[:50]} "
                        f"(pk={publikacja_pk})"
                    )
                else:
                    results_before = przelicz_metryki_dla_publikacji(publikacja)
                    if metrics_before_cache is not None:
                        metrics_before_cache[publikacja_pk] = results_before
                        logger.debug(
                            f"Cache MISS dla publikacji {publikacja.tytul_oryginalny[:50]} "
                            f"(pk={publikacja_pk}), zapisano"
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
                        f"Brak metryk PRZED dla autora B {autor_currently_using} "
                        f"w dyscyplinie {dyscyplina_naukowa}"
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
                from django.db import connection

                connection.cursor().execute("SELECT 1")  # Flush pending queries

                # 4. Przelicz metryki PO odpięciu
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
                        f"Brak metryk PO dla autora B {autor_currently_using} "
                        f"w dyscyplinie {dyscyplina_naukowa}"
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
                punkty_roznica_a = punkty_a_after - punkty_a_before
                sloty_roznica_a = slot_a_after - slot_a_before

                punkty_roznica_b = punkty_b_after - punkty_b_before
                sloty_roznica_b = slot_b_after - slot_b_before

                # Sprawdź czy praca była wykazana dla A
                if metryka_a_before is not None:
                    rekord_id = publikacja.pk
                    prace_nazbierane_a = metryka_a_before.prace_nazbierane or []
                    prace_nazbierane_a_tuples = [
                        tuple(p) if isinstance(p, list) else p
                        for p in prace_nazbierane_a
                    ]
                    praca_byla_wykazana_dla_a = rekord_id in prace_nazbierane_a_tuples
                else:
                    praca_byla_wykazana_dla_a = False

                # Oblicz stratę A i zysk B
                if not praca_byla_wykazana_dla_a:
                    punkty_strata_a = Decimal("0")
                else:
                    punkty_strata_a = abs(punkty_roznica_a)

                punkty_zysk_b = (
                    punkty_roznica_b if punkty_roznica_b > 0 else Decimal("0")
                )

                # Odpięcie ma sens gdy instytucja zyskuje więcej niż traci
                makes_sense = punkty_zysk_b > punkty_strata_a

                logger.debug(
                    f"Symulacja odpięcia dla {autor_a} -> {autor_currently_using}: "
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
        return None
