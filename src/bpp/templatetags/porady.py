from django import template

from bpp.porady import PORADY, wersja_porad

register = template.Library()


@register.inclusion_tag("browse/pasek_porad.html")
def pasek_porad():
    """Pasek „Porady BPP” (strona główna) — rotujące porady z przyciskiem ×."""
    return {"porady": PORADY, "wersja_porad": wersja_porad()}
