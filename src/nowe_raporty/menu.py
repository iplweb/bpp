"""Data-driven menu raportów (płaska lista) z cache.

Cache trzyma odchudzoną listę aktywnych ``DefinicjaRaportu`` (z prefetch M2M),
a filtr ``widoczny_dla`` leci per-request w Pythonie (bez N+1). Cache jest
odrębny od ``bpp_uczelnia`` i inwalidowany na zapis/zmianę ``DefinicjaRaportu``.
"""

from django.core.cache import cache

from .models import DefinicjaRaportu

CACHE_KEY = "nowe_raporty_menu_definicje"
CACHE_TTL = 3600


def _aktywne_definicje():
    definicje = cache.get(CACHE_KEY)
    if definicje is None:
        definicje = list(
            DefinicjaRaportu.objects.filter(aktywny=True)
            .prefetch_related("wymagane_grupy", "uczelnie")
            .order_by("kolejnosc", "nazwa")
        )
        cache.set(CACHE_KEY, definicje, CACHE_TTL)
    return definicje


def widoczne_raporty(request):
    """Aktywne definicje widoczne dla danego requestu (posortowane)."""
    return [d for d in _aktywne_definicje() if d.widoczny_dla(request)]


def raporty_menu(request):
    """Context processor: lista widocznych raportów dla top_bar."""
    return {"raporty_menu": widoczne_raporty(request)}


def wyczysc_cache_menu(*args, **kwargs):
    cache.delete(CACHE_KEY)
