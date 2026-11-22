"""Źródło zmiany rewizji django-reversion (FD#587) — stałe i kontekst.

Bez importu modeli: korzystają z niego ``bpp.wersjonowanie``, middleware
i ``historia_zmian.models``.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.dispatch import Signal

ZRODLO_ADMIN = "admin"
ZRODLO_STRONA = "strona"
ZRODLO_NARZEDZIE = "narzedzie"
ZRODLO_API = "api"
ZRODLO_SYSTEM = "system"

ZRODLA_ZMIAN = (
    (ZRODLO_ADMIN, "moduł redagowania"),
    (ZRODLO_STRONA, "strona (np. edycja profilu)"),
    (ZRODLO_NARZEDZIE, "import lub narzędzie"),
    (ZRODLO_API, "API / MCP"),
    (ZRODLO_SYSTEM, "system (zadanie w tle, polecenie)"),
)

_zrodlo_zmian = ContextVar("zrodlo_zmian", default=None)

#: Wysyłany po hurtowym zapisie rewizji (``zapisz_wersje_osobno``), który
#: omija ``post_revision_commit``. Argument: ``rewizje`` (lista).
wersje_zapisane_hurtowo = Signal()


@contextmanager
def zrodlo_zmian(zrodlo, *, aplikacja=None):
    """Rewizje zapisane w bloku dostaną źródło ``zrodlo`` (``ZRODLO_*``)
    i — opcjonalnie — aplikację OAuth (obiekt z ``client_id`` i ``name``,
    np. ``oauth2_provider.models.Application``). Wewnętrzny blok wygrywa."""
    token = _zrodlo_zmian.set(
        {
            "zrodlo": zrodlo,
            "aplikacja_client_id": getattr(aplikacja, "client_id", "") or "",
            "aplikacja_nazwa": getattr(aplikacja, "name", "") or "",
        }
    )
    try:
        yield
    finally:
        _zrodlo_zmian.reset(token)


def biezace_zrodlo_zmian():
    """Źródło zmiany z kontekstu; poza żadnym kontekstem — system."""
    return _zrodlo_zmian.get() or {
        "zrodlo": ZRODLO_SYSTEM,
        "aplikacja_client_id": "",
        "aplikacja_nazwa": "",
    }
