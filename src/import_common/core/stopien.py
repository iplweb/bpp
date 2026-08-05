"""Klasyfikacja stopni służbowych z importu pracowników.

Mirror ``import_common/core/tytul.py`` — stopnie mają kropki (``st. kpt.``),
więc dopasowanie DOKŁADNE liczymy po ``normalize_stopien`` OBU stron (nie
SQL ``iexact``). Próg zgadywania jak dla tytułów (0.85 — krótkie stringi).
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from bpp.models import StopienSluzbowy

PROG_ZGADYWANIA_STOPNIA = 0.85

STATUS_STOPIEN_TWARDY = "twardy"
STATUS_STOPIEN_ZGADYWANIE = "zgadywanie"
STATUS_STOPIEN_BRAK = "brak"


def normalize_stopien(s):
    """Kanonikalizacja DO PORÓWNANIA: lower + strip + zwinięcie spacji +
    usunięcie kropek. ``None``/pusty → ``""``."""
    if not s:
        return ""
    return " ".join(s.lower().replace(".", "").split())


def sklasyfikuj_stopien(stopien_str, *, prog=PROG_ZGADYWANIA_STOPNIA):
    """Zwraca ``(StopienSluzbowy|None, status, similarity|None)`` bez rzucania."""
    if not stopien_str:
        return None, STATUS_STOPIEN_BRAK, None
    norm = normalize_stopien(stopien_str)
    if not norm:
        return None, STATUS_STOPIEN_BRAK, None

    for s in StopienSluzbowy.objects.all():
        if norm in (normalize_stopien(s.nazwa), normalize_stopien(s.skrot)):
            return s, STATUS_STOPIEN_TWARDY, None

    best = (
        StopienSluzbowy.objects.annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", norm),
                TrigramSimilarity("skrot", norm),
            )
        )
        .order_by("-sim")
        .first()
    )
    if best is not None and best.sim is not None and best.sim >= prog:
        return best, STATUS_STOPIEN_ZGADYWANIE, float(best.sim)
    return None, STATUS_STOPIEN_BRAK, None


def zaproponuj_skrot_stopnia(s):
    """Domyślny skrót nowego stopnia: forma źródłowa przycięta do 128."""
    return (s or "").strip()[:128]
