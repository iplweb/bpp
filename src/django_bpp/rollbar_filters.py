"""Filtry poziomów wyjątków dla Rollbara (``exception_level_filters``).

pyrollbar pozwala przypisać klasie wyjątku poziom ``"ignored"`` — taki wyjątek
nie jest w ogóle wysyłany (``rollbar._is_ignored``). Używamy tego wyłącznie
tam, gdzie raport NIE niesie informacji: dana instalacja ma znaną, trwałą awarię
poza naszym kodem, a każde wystąpienie zakłada w Rollbarze osobny item.

Wyodrębnione z ``settings.base`` jako czysta funkcja, żeby dało się to
przetestować bez przeładowywania ustawień Django.
"""

from __future__ import annotations

import smtplib


def zbuduj_exception_level_filters(*, ignoruj_bledy_poczty: bool = False):
    """Zwraca listę par ``(klasa_wyjątku, poziom)`` dla ``ROLLBAR``.

    :param ignoruj_bledy_poczty: wycisza CAŁĄ rodzinę ``smtplib.SMTPException``
        (uwierzytelnianie, połączenie, odrzuceni odbiorcy). Włączane
        per-instalacja przez ``DJANGO_BPP_ROLLBAR_IGNORE_SMTP_ERRORS`` i tylko
        tam, gdzie administratorzy poczty mają znaną awarię po swojej stronie,
        a my nie mamy jak jej naprawić. Domyślnie WYŁĄCZONE — na pozostałych
        instalacjach niedziałająca poczta to realny problem (nie idą
        powiadomienia o zgłoszeniach publikacji) i chcemy o niej wiedzieć.
    """
    filters: list[tuple[type[BaseException], str]] = []

    if ignoruj_bledy_poczty:
        filters.append((smtplib.SMTPException, "ignored"))

    return filters
