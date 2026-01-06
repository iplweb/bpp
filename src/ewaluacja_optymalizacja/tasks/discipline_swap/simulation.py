"""Symulacja zamiany dyscypliny i obliczanie różnicy punktów."""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def simulate_discipline_swap(autor_assignment, target_discipline):
    """
    Symuluje zamianę dyscypliny autora i oblicza różnicę punktów.

    Args:
        autor_assignment: Obiekt Wydawnictwo_Ciagle_Autor lub Wydawnictwo_Zwarte_Autor
        target_discipline: Docelowa Dyscyplina_Naukowa (do zamiany)

    Returns:
        dict: {
            'points_before': Decimal - punkty przed zamianą,
            'points_after': Decimal - punkty po zamianie,
            'point_improvement': Decimal - różnica punktów (after - before),
            'makes_sense': bool - True jeśli zamiana zwiększa punkty,
        }
        lub None jeśli symulacja nie powiodła się
    """
    from django.db import transaction

    from bpp.models.sloty.core import IPunktacjaCacher
    from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

    try:
        with transaction.atomic():
            publikacja = autor_assignment.rekord
            original_discipline = autor_assignment.dyscyplina_naukowa

            sid = transaction.savepoint()

            try:
                # 1. Oblicz punkty PRZED zamianą
                results_before = przelicz_metryki_dla_publikacji(publikacja)
                points_before = _sum_total_points(results_before)

                # 2. Wykonaj zamianę dyscypliny
                autor_assignment.dyscyplina_naukowa = target_discipline
                autor_assignment.save()

                # 3. Przebuduj cache punktacji
                cacher = IPunktacjaCacher(publikacja)
                cacher.removeEntries()
                cacher.rebuildEntries()

                # Wymuś odświeżenie cache w Django ORM
                from django.db import connection

                connection.cursor().execute("SELECT 1")

                # 4. Oblicz punkty PO zamianie
                results_after = przelicz_metryki_dla_publikacji(publikacja)
                points_after = _sum_total_points(results_after)

                # Oblicz różnicę
                point_improvement = points_after - points_before
                makes_sense = point_improvement > Decimal("0")

                logger.debug(
                    f"Symulacja zamiany dla {autor_assignment.autor}: "
                    f"{original_discipline} -> {target_discipline}: "
                    f"przed={points_before}, po={points_after}, "
                    f"poprawa={point_improvement}, sens={makes_sense}"
                )

                return {
                    "points_before": points_before,
                    "points_after": points_after,
                    "point_improvement": point_improvement,
                    "makes_sense": makes_sense,
                }

            finally:
                # ZAWSZE rollback - przywróć stan przed symulacją
                transaction.savepoint_rollback(sid)

    except Exception as e:
        logger.error(f"Błąd podczas symulacji zamiany dyscypliny: {e}", exc_info=True)
        return None


def _sum_total_points(metryki_results):
    """
    Sumuje całkowitą punktację ze wszystkich metryk publikacji.

    Args:
        metryki_results: Lista krotek (autor, dyscyplina, metryka) z
                         przelicz_metryki_dla_publikacji

    Returns:
        Decimal: Suma punktów nazbieranych ze wszystkich metryk
    """
    total = Decimal("0")

    for _autor, _dyscyplina, metryka in metryki_results:
        if metryka and metryka.punkty_nazbierane:
            total += metryka.punkty_nazbierane

    return total
