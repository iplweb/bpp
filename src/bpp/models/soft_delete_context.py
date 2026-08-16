"""Kanał atrybucji „kto i dlaczego" dla operacji soft-delete.

DLACZEGO THREAD-LOCAL, A NIE ARGUMENT: sygnały pakietu
``django-soft-delete`` (``post_soft_delete``, ``post_restore``,
``post_hard_delete``) niosą wyłącznie ``sender`` i ``instance`` — usera ani
powodu nie przekazują i nie da się ich dołożyć bez forka pakietu. Receivery
z ``bpp/receivers/soft_delete.py`` są jednak JEDYNYM miejscem, w którym
powstaje ``SoftDeleteLog``, więc user musi tam jakoś dojechać. Kontekst
ustawiany przez ``delete(user=, reason=)`` tuż przed wysłaniem sygnału jest
najwęższym kanałem, jaki załatwia sprawę dla wszystkich modeli naraz.

KONTRAKT Z REVERSION: to ten SAM punkt wstrzyknięcia, w który wepnie się
przyszłe ``reversion.set_user`` — jeden hook, nie dwa konkurencyjne.

Operacje bez zalogowanego użytkownika (scalanie duplikatów, celery, gołe
``.delete()`` w skryptach) po prostu nie wchodzą w kontekst: akcesory
zwracają wtedy ``None``/``""`` i log powstaje bez atrybucji. To jest
poprawny wynik, nie błąd — „nie wiadomo kto" jest uczciwszą odpowiedzią niż
podstawienie pierwszego lepszego konta.
"""

import threading
from contextlib import contextmanager

__all__ = [
    "soft_delete_context",
    "current_soft_delete_user",
    "current_soft_delete_reason",
]

_ctx = threading.local()


@contextmanager
def soft_delete_context(user=None, reason=""):
    """Ustawia thread-local user/reason na czas soft-delete / restore.

    Receivery czytają to przez ``current_soft_delete_user()`` /
    ``current_soft_delete_reason()``.

    REENTRANCJA JEST WYMAGANA, nie „miła": soft-delete publikacji kasuje
    najpierw swoje wiersze ``*_Autor`` (wąska kaskada fazy 02), a każdy
    z nich wchodzi w ten kontekst ponownie. Zapamiętanie i odtworzenie
    poprzednich wartości sprawia, że kaskada dziedziczy usera rodzica,
    zamiast go wyzerować w połowie operacji.

    Sprzątanie siedzi w ``finally``, bo ``delete()`` bywa przerywany —
    guard fazy 04 rzuca ``ProtectedError`` dla autora z pracami. Kontekst,
    który przeciekłby po wyjątku, przypisałby cudzego usera NASTĘPNEJ
    operacji w tym wątku (w produkcji: kolejnemu requestowi na tym samym
    workerze). Byłby to błąd cichy i nie do wykrycia po fakcie.

    POMINIĘTY ARGUMENT DZIEDZICZY, NIE ZERUJE. Wejście bez ``user``
    zachowuje usera z kontekstu zewnętrznego. Bez tej reguły oba
    przewidziane sposoby atrybucji wykluczałyby się nawzajem: ``delete()``
    (fazy 02/04) zakłada ten kontekst ZAWSZE, więc wywołanie bez ``user=``
    wewnątrz jawnego ``soft_delete_context(user=X)`` wyzerowałoby X i
    operacja trafiłaby do logu jako niczyja. Opakowanie, które nie wnosi
    informacji, nie ma prawa jej niszczyć — ``None`` znaczy tu „nie wiem",
    a nie „wiem, że nikt".
    """
    prev_user = getattr(_ctx, "user", None)
    prev_reason = getattr(_ctx, "reason", "")
    _ctx.user = user if user is not None else prev_user
    _ctx.reason = reason if reason else prev_reason
    try:
        yield
    finally:
        _ctx.user = prev_user
        _ctx.reason = prev_reason


def current_soft_delete_user():
    """User bieżącej operacji soft-delete albo ``None`` poza kontekstem."""
    return getattr(_ctx, "user", None)


def current_soft_delete_reason():
    """Powód bieżącej operacji soft-delete albo ``""`` poza kontekstem."""
    return getattr(_ctx, "reason", "")
