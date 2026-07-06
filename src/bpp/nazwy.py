"""Źródło lematów (mianownik l.poj.) dla generycznych nazw struktury.

Odmianę zapewnia ``polish-inflection`` — tu dostarczamy tylko mianownik,
z per-install override w modelu ``Rzeczownik`` albo z wartości domyślnej.
"""

DOMYSLNE_LEMATY = {
    "UCZELNIA": "uczelnia",
    "WYDZIAL": "wydział",
    "JEDNOSTKA": "jednostka",
}


def lemat(uid):
    """Mianownik (lemat) dla ``uid``: override z ``Rzeczownik`` albo default."""
    from bpp.models import Rzeczownik

    row = Rzeczownik.objects.filter(uid=uid).first()
    return row.m if row is not None else DOMYSLNE_LEMATY[uid]
