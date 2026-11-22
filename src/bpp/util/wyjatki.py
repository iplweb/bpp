"""Logowanie „połykanych" wyjątków.

Gdy w bloku ``except`` świadomie kontynuujemy działanie (zwracamy fallback,
pokazujemy userowi „wystąpił nieznany błąd", pomijamy element) — zamiast ciszy
wołamy :func:`zaloguj_polkniety_wyjatek`. Pełny traceback trafia do logów,
a dla ścieżek produkcyjnych również do monitoringu błędów (Rollbar i/lub
Sentry/GlitchTip — patrz :mod:`bpp.zglaszanie_bledow`), więc wiadomo *co* się
stało.

Helper MUSI być wywołany wewnątrz aktywnego bloku ``except`` — ``logger.exception``
oraz ``sys.exc_info()`` odczytują obsługiwany właśnie wyjątek z kontekstu.
"""

import logging
import sys

from bpp.zglaszanie_bledow import capture_exception

_domyslny_logger = logging.getLogger("bpp.polkniete_wyjatki")


def zaloguj_polkniety_wyjatek(komunikat, *, logger=None, do_monitoringu=True):
    """Zaloguj wyjątek obsługiwany w bieżącym bloku ``except``.

    :param komunikat: opis po polsku — co robiliśmy, gdy padło.
    :param logger: logger modułu wywołującego (dla origin w logach);
        domyślnie wspólny ``bpp.polkniete_wyjatki``.
    :param do_monitoringu: czy zgłaszać do monitoringu błędów (True dla
        web/task/admin, False dla narzędzi CLI i benignych fallbacków — log
        i tak powstaje).
    """
    log = logger or _domyslny_logger
    log.exception(komunikat)

    if do_monitoringu:
        # capture_exception nie rzuca — błąd wysyłki loguje sam.
        capture_exception(sys.exc_info())
