"""Konta staff bez przypisanych uczelni — jedna definicja reguły.

Pusta relacja ``accessible_uczelnie`` oznacza dostęp do panelu
administracyjnego wszystkich uczelni (kompatybilność wsteczna). Przy więcej
niż jednej uczelni operator powinien o takich kontach wiedzieć. Z tej samej
reguły korzystają: system check ``bpp.W001`` (``bpp.checks``), filtr listy
użytkowników w adminie (``bpp.admin.filters``) i komunikat dla superusera
po zalogowaniu (``ostrzez_superusera_po_zalogowaniu``).
"""

import logging

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

logger = logging.getLogger(__name__)

#: Parametr GET filtra ``KontaStaffBezUczelniFilter`` w adminie użytkowników.
FILTR_PARAMETR = "dostep_do_uczelni"
FILTR_WARTOSC_BRAK = "brak"


def konta_staff_bez_uczelni():
    """Aktywne konta ``is_staff`` (bez superuserów) z pustym
    ``accessible_uczelnie``."""
    from bpp.models import BppUser

    return BppUser.objects.filter(
        is_active=True,
        is_staff=True,
        is_superuser=False,
        accessible_uczelnie__isnull=True,
    ).distinct()


def jest_wiele_uczelni():
    from bpp.models import Uczelnia

    return Uczelnia.objects.count() > 1


def url_listy_kont_bez_uczelni():
    return (
        reverse("admin:bpp_bppuser_changelist")
        + f"?{FILTR_PARAMETR}={FILTR_WARTOSC_BRAK}"
    )


def ostrzez_superusera_po_zalogowaniu(sender, request, user, **kwargs):
    """Handler ``user_logged_in``: superuser dostaje komunikat z liczbą kont
    staff bez przypisanych uczelni i linkiem do przefiltrowanej listy.

    Nigdy nie przerywa logowania — błędy są logowane.
    """
    if request is None or not getattr(user, "is_superuser", False):
        return

    try:
        # Savepoint: błąd zapytania nie może zepsuć transakcji żądania.
        with transaction.atomic():
            if not jest_wiele_uczelni():
                return
            liczba = konta_staff_bez_uczelni().count()
        if not liczba:
            return
        url = url_listy_kont_bez_uczelni()
    except (DatabaseError, NoReverseMatch):
        # Brak tabel / niezainstalowany admin — logowanie ma przejść.
        logger.warning(
            "Nie udało się sprawdzić kont staff bez przypisanych uczelni "
            "po zalogowaniu superusera.",
            exc_info=True,
        )
        return
    except Exception:
        # Komunikat jest informacyjny — żaden błąd nie może zablokować
        # logowania. Pełny traceback trafia do logów.
        logger.exception("Nieoczekiwany błąd przy sprawdzaniu kont staff bez uczelni.")
        return

    messages.warning(
        request,
        format_html(
            "W systemie jest więcej niż jedna uczelnia, a liczba aktywnych kont "
            "z dostępem do panelu (bez superuserów) bez przypisanych uczelni "
            "wynosi {}. Takie konta mają dostęp do panelu administracyjnego "
            'wszystkich uczelni. <a href="{}">Pokaż te konta</a>.',
            liczba,
            url,
        ),
        fail_silently=True,
    )
