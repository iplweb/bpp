"""Przypisywanie dyscyplin z PBN do Autor_Dyscyplina.

Slot-aware (dyscyplina_naukowa + subdyscyplina_naukowa), odporne na konflikty:
nigdy nie podnosi wyjątku ani nie nadpisuje ręcznych procentów — zwraca enum
wyniku, a wołający decyduje o logu/raporcie.
"""

from __future__ import annotations

import enum
from decimal import Decimal

from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa

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


def przypisz_dyscypline_pbn(
    autor: Autor, rok: int, dyscyplina: Dyscyplina_Naukowa
) -> WynikPrzypisaniaDyscypliny:
    """Przypisz `dyscyplina` autorowi na `rok`, korzystając z dwóch slotów.

    Procenty uzupełniamy TYLKO gdy brak danych użytkownika: 100% dla jednej
    dyscypliny, 50/50 dla dwóch. Ręcznych procentów nie nadpisujemy.

    `get_or_create` jest odporne na wyścig na unique_together (rok, autor):
    wewnętrznie łapie IntegrityError w savepoincie i ponawia get, więc kontrakt
    "nigdy nie podnosi" obowiązuje też przy współbieżnych wołaniach.
    """
    ad, utworzono = Autor_Dyscyplina.objects.get_or_create(
        autor=autor,
        rok=rok,
        defaults={
            "dyscyplina_naukowa": dyscyplina,
            "procent_dyscypliny": PROCENT_100,
        },
    )
    if utworzono:
        return WynikPrzypisaniaDyscypliny.UTWORZONO

    if dyscyplina.pk in (ad.dyscyplina_naukowa_id, ad.subdyscyplina_naukowa_id):
        return WynikPrzypisaniaDyscypliny.BRAK_ZMIAN

    if ad.subdyscyplina_naukowa_id is None:
        ad.subdyscyplina_naukowa = dyscyplina
        update_fields = ["subdyscyplina_naukowa"]
        if _procenty_wygladaja_na_auto(ad):
            ad.procent_dyscypliny = PROCENT_50
            ad.procent_subdyscypliny = PROCENT_50
            update_fields += ["procent_dyscypliny", "procent_subdyscypliny"]
        # else: zostaw ręczne procenty głównej, sub bez procentu (do weryfikacji)
        ad.save(update_fields=update_fields)
        return WynikPrzypisaniaDyscypliny.DODANO_SUB

    return WynikPrzypisaniaDyscypliny.KONFLIKT_BRAK_MIEJSCA
