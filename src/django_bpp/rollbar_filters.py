"""Filtry poziomów wyjątków dla Rollbara (``exception_level_filters``).

pyrollbar pozwala przypisać klasie wyjątku poziom ``"ignored"`` — taki wyjątek
nie jest w ogóle wysyłany. Używamy tego wyłącznie tam, gdzie awaria jest znana,
zgłoszona i leży POZA naszym kodem, więc raport nie niesie już informacji.

Dlaczego kodem, a nie „mute" w interfejsie Rollbara: mute jest per item, a item
przepada przy zmianie hasha — wystarczyła podbitka pyrollbara 1.3.0 → 1.4.0,
żeby ten sam błąd SMTP odszczepił się w drugi item (#379 → #1554). Wyciszenie
w kodzie jest trwałe i, co ważniejsze, WIDOCZNE w repozytorium: da się je
znaleźć gitem i cofnąć, gdy klient naprawi pocztę.

Wyodrębnione z ``settings.base`` jako czysta funkcja, żeby dało się to
przetestować bez przeładowywania ustawień Django.
"""

from __future__ import annotations

import smtplib


def zbuduj_exception_level_filters(
    *, ignoruj_bledy_uwierzytelniania_smtp: bool = False
) -> list[tuple[type[BaseException], str]]:
    """Zwraca listę par ``(klasa_wyjątku, poziom)`` dla ``ROLLBAR``.

    :param ignoruj_bledy_uwierzytelniania_smtp: wycisza ``SMTPAuthenticationError``
        — i TYLKO ją. Włączane per instalacja przez
        ``DJANGO_BPP_ROLLBAR_IGNORE_SMTP_AUTH_ERRORS``, domyślnie WYŁĄCZONE.

        Celowo NIE wyciszamy całej rodziny ``smtplib.SMTPException``:
        ``SMTPRecipientsRefused`` to zły adres w NASZEJ bazie, a
        ``SMTPSenderRefused`` to nasza konfiguracja ``DEFAULT_FROM_EMAIL`` —
        jedno i drugie jest do naprawienia po naszej stronie i chcemy o tym
        wiedzieć także na instalacji z zepsutą pocztą.

        UWAGA: to ustawienie działa na CAŁY PROCES. Przy konfiguracji
        wielotenantowej (``DJANGO_BPP_HOSTNAMES``) wyciszy błędy poczty
        wszystkim uczelniom obsługiwanym przez ten proces.
    """
    filters: list[tuple[type[BaseException], str]] = []

    if ignoruj_bledy_uwierzytelniania_smtp:
        filters.append((smtplib.SMTPAuthenticationError, "ignored"))

    return filters
