"""Kto może używać konfiguratora wyglądu.

Superużytkownik albo obsługa (``is_staff``) w grupie „web” lub
„administracja”. Ta sama reguła dla widoków konfiguratora, trybu podglądu,
przymiarki i linków w menu (strona: „redagowanie”, admin: „WWW”).
„Zastosuj dla wszystkich” dodatkowo wymaga superużytkownika.
"""

from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied

from bpp.const import GR_ADMINISTRACJA, GR_WEB

GRUPY_KONFIGURATORA = (GR_WEB, GR_ADMINISTRACJA)


def moze_konfigurowac_wyglad(user):
    if user is None or not user.is_authenticated or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    # Wynik zapamiętany na obiekcie użytkownika — sprawdzane kilka razy na
    # jedno żądanie (menu, procesor kontekstu, middleware podglądu).
    wynik = getattr(user, "_bpp_moze_konfigurowac_wyglad", None)
    if wynik is None:
        wynik = user.groups.filter(name__in=GRUPY_KONFIGURATORA).exists()
        user._bpp_moze_konfigurowac_wyglad = wynik
    return wynik


def konfigurator_wymagany(widok):
    """Jak ``staff_member_required`` (niezalogowany → logowanie), a obsługa
    spoza grup konfiguratora dostaje 403."""

    @wraps(widok)
    def opakowany(request, *args, **kwargs):
        if not moze_konfigurowac_wyglad(request.user):
            raise PermissionDenied
        return widok(request, *args, **kwargs)

    return staff_member_required(opakowany)
