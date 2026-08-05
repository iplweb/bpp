"""Klasyfikacja stanowisk dydaktycznych z importu pracowników.

Mirror ``import_common/core/stopien.py`` (identyczna mechanika, model
``StanowiskoDydaktyczne``). Porównanie po ``normalize_stanowisko``, trigram
≥0.85.
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from bpp.models import StanowiskoDydaktyczne

PROG_ZGADYWANIA_STANOWISKA = 0.85

STATUS_STANOWISKO_TWARDY = "twardy"
STATUS_STANOWISKO_ZGADYWANIE = "zgadywanie"
STATUS_STANOWISKO_BRAK = "brak"


def normalize_stanowisko(s):
    if not s:
        return ""
    return " ".join(s.lower().replace(".", "").split())


def sklasyfikuj_stanowisko(stanowisko_str, *, prog=PROG_ZGADYWANIA_STANOWISKA):
    if not stanowisko_str:
        return None, STATUS_STANOWISKO_BRAK, None
    norm = normalize_stanowisko(stanowisko_str)
    if not norm:
        return None, STATUS_STANOWISKO_BRAK, None

    for s in StanowiskoDydaktyczne.objects.all():
        if norm in (normalize_stanowisko(s.nazwa), normalize_stanowisko(s.skrot)):
            return s, STATUS_STANOWISKO_TWARDY, None

    best = (
        StanowiskoDydaktyczne.objects.annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", norm),
                TrigramSimilarity("skrot", norm),
            )
        )
        .order_by("-sim")
        .first()
    )
    if best is not None and best.sim is not None and best.sim >= prog:
        return best, STATUS_STANOWISKO_ZGADYWANIE, float(best.sim)
    return None, STATUS_STANOWISKO_BRAK, None


def zaproponuj_skrot_stanowiska(s):
    return (s or "").strip()[:128]
