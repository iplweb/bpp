"""Wersja faviconu — unieważnia cache przy każdej zmianie ikony.

``bare.html`` trzyma ``<link>``-i faviconu we fragmencie
``{% cache 3600 favicon host FAVICON_WERSJA %}``. Wersja podbija się przy
zapisie/usunięciu ``Favicon``, ``FaviconImg`` i ``Uczelnia`` (pole
``favicon_ico``) — z konfiguratora wyglądu, admina uczelni czy admina
biblioteki ``favicon`` — więc nowa ikona pojawia się od razu, bez czekania
na wygaśnięcie fragmentu.
"""

from django.core.cache import cache

KLUCZ = "bpp:favicon:wersja"


def wersja():
    return cache.get(KLUCZ, 0)


def podbij(**kwargs):
    """Receiver sygnałów post_save / post_delete."""
    try:
        cache.incr(KLUCZ)
    except ValueError:
        # Klucza jeszcze nie ma (incr wymaga istniejącego) — zakładamy go.
        cache.set(KLUCZ, 1, None)
