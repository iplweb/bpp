from django import template

from ..wzbogacanie.dodawanie_autorow import jest_sesja_wzbogacania, rekord_sesji

register = template.Library()


@register.simple_tag
def wzbogacany_rekord(session):
    """Dla sesji dodającej autorów do istniejącego rekordu (FD#517):
    ``{"rekord": …, "powrot": adres porównania}``; dla zwykłej — ``None``."""
    if session is None or not jest_sesja_wzbogacania(session):
        return None
    from ..wzbogacanie.dodawanie_autorow import KLUCZ

    return {
        "rekord": rekord_sesji(session),
        "powrot": session.matched_data[KLUCZ].get("powrot") or "",
        "porzuc": session.matched_data[KLUCZ].get("porzuc") or "",
    }
