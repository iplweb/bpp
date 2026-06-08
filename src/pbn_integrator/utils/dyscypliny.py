"""Przypisywanie dyscyplin z PBN do Autor_Dyscyplina.

Slot-aware (dyscyplina_naukowa + subdyscyplina_naukowa), odporne na konflikty:
nigdy nie podnosi wyjątku ani nie nadpisuje ręcznych procentów — zwraca enum
wyniku, a wołający decyduje o logu/raporcie.
"""

from __future__ import annotations

import enum
import logging
from decimal import Decimal

from django.db import transaction

from bpp.models import Autor_Dyscyplina

logger = logging.getLogger(__name__)

PROCENT_100 = Decimal("100.00")
PROCENT_50 = Decimal("50.00")


class WynikPrzypisaniaDyscypliny(enum.Enum):
    BRAK_ZMIAN = "brak_zmian"
    UTWORZONO = "utworzono"
    DODANO_SUB = "dodano_sub"
    KONFLIKT_BRAK_MIEJSCA = "konflikt_brak_miejsca"


def _procenty_wygladaja_na_auto(ad: Autor_Dyscyplina) -> bool:
    """True, gdy procenty nie wyglądają na ręczny podział użytkownika.

    Traktujemy jako "auto" sytuację: brak procentu głównej dyscypliny, albo
    główna = 100% przy pustej sub (to nasz własny wynik auto-utworzenia).
    """
    if ad.procent_dyscypliny is None:
        return True
    return ad.procent_dyscypliny == PROCENT_100 and ad.procent_subdyscypliny is None


def przypisz_dyscypline_pbn(autor, rok, dyscyplina) -> WynikPrzypisaniaDyscypliny:
    """Przypisz `dyscyplina` autorowi na `rok`, korzystając z dwóch slotów.

    Procenty uzupełniamy TYLKO gdy brak danych użytkownika: 100% dla jednej
    dyscypliny, 50/50 dla dwóch. Ręcznych procentów nie nadpisujemy.
    """
    try:
        ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
    except Autor_Dyscyplina.DoesNotExist:
        with transaction.atomic():
            Autor_Dyscyplina.objects.create(
                autor=autor,
                rok=rok,
                dyscyplina_naukowa=dyscyplina,
                procent_dyscypliny=PROCENT_100,
            )
        return WynikPrzypisaniaDyscypliny.UTWORZONO

    if dyscyplina.pk in (ad.dyscyplina_naukowa_id, ad.subdyscyplina_naukowa_id):
        return WynikPrzypisaniaDyscypliny.BRAK_ZMIAN

    if ad.subdyscyplina_naukowa_id is None:
        ad.subdyscyplina_naukowa = dyscyplina
        if _procenty_wygladaja_na_auto(ad):
            ad.procent_dyscypliny = PROCENT_50
            ad.procent_subdyscypliny = PROCENT_50
        # else: zostaw ręczne procenty głównej, sub bez procentu (do weryfikacji)
        with transaction.atomic():
            ad.save()
        return WynikPrzypisaniaDyscypliny.DODANO_SUB

    return WynikPrzypisaniaDyscypliny.KONFLIKT_BRAK_MIEJSCA
