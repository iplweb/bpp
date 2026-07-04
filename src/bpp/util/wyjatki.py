"""Logowanie „połykanych" wyjątków.

Gdy w bloku ``except`` świadomie kontynuujemy działanie (zwracamy fallback,
pokazujemy userowi „wystąpił nieznany błąd", pomijamy element) — zamiast ciszy
wołamy :func:`zaloguj_polkniety_wyjatek`. Pełny traceback trafia do logów,
a dla ścieżek produkcyjnych również do Rollbara, więc wiadomo *co* się stało.

Helper MUSI być wywołany wewnątrz aktywnego bloku ``except`` — ``logger.exception``
oraz ``sys.exc_info()`` odczytują obsługiwany właśnie wyjątek z kontekstu.
"""

import logging
import sys

try:
    import rollbar
except ImportError:  # rollbar to zależność produkcyjna, ale nie wymuszamy jej
    rollbar = None

_domyslny_logger = logging.getLogger("bpp.polkniete_wyjatki")


def zaloguj_polkniety_wyjatek(komunikat, *, logger=None, do_rollbar=True):
    """Zaloguj wyjątek obsługiwany w bieżącym bloku ``except``.

    :param komunikat: opis po polsku — co robiliśmy, gdy padło.
    :param logger: logger modułu wywołującego (dla origin w logach);
        domyślnie wspólny ``bpp.polkniete_wyjatki``.
    :param do_rollbar: czy raportować do Rollbara (True dla web/task/admin,
        False dla narzędzi CLI i benignych fallbacków — log i tak powstaje).
    """
    log = logger or _domyslny_logger
    log.exception(komunikat)

    if do_rollbar and rollbar is not None:
        try:
            rollbar.report_exc_info(sys.exc_info())
        except Exception:
            # Rollbar nieskonfigurowany / niedostępny — traceback jest już
            # w logach powyżej, więc tylko odnotowujemy nieudany raport.
            log.debug("Nie udało się zaraportować wyjątku do Rollbara", exc_info=True)
