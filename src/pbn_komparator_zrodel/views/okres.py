"""Okres ewaluacji w filtrach komparatora źródeł PBN.

Okres wybrany na pasku okresu (albo w adresie URL,
``/komparator-zrodel-pbn/2026-2030/...``) wyznacza domyślny zakres lat listy
i filtr „tylko źródła z publikacjami w okresie”. Okres czytamy wyłącznie
w widokach (z żądania) — zadania Celery dostają gotowe ``pk`` rekordów.
"""

from django.db.models import Exists, OuterRef

from bpp.models import Wydawnictwo_Ciagle
from ewaluacja_common.okres import lata_okresu  # noqa: F401 (re-eksport)

#: Parametr GET filtra „tylko źródła z publikacjami w wybranym okresie”.
PARAM_PUBLIKACJE_W_OKRESIE = "tylko_z_publikacjami_w_okresie"

#: Dawna nazwa tego parametru (lata 2022–2025 na sztywno) — nadal działa,
#: żeby stare zakładki/linki nie gubiły filtra.
PARAM_PUBLIKACJE_W_OKRESIE_DAWNY = "bez_publikacji_2022_2025"


def tylko_z_publikacjami_w_okresie(request):
    """Czy zaznaczono filtr „tylko źródła z publikacjami w okresie”
    (checkbox: obecny w GET, gdy zaznaczony)."""
    return (
        PARAM_PUBLIKACJE_W_OKRESIE in request.GET
        or PARAM_PUBLIKACJE_W_OKRESIE_DAWNY in request.GET
    )


def filtruj_publikacje_w_okresie(queryset, rok_od, rok_do):
    """Zostaw rozbieżności źródeł, które mają publikacje (wydawnictwa ciągłe)
    z lat ``rok_od``–``rok_do``."""
    ma_publikacje = Wydawnictwo_Ciagle.objects.filter(
        zrodlo_id=OuterRef("zrodlo_id"), rok__gte=rok_od, rok__lte=rok_do
    )
    return queryset.filter(Exists(ma_publikacje))
