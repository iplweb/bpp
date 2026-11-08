"""Stałe wpisy słowników, po które modele sięgają same (bez kolumny FK).

``Patent``, ``Praca_Doktorska`` i ``Praca_Habilitacyjna`` nie mają kolumny
``charakter_formalny`` (``Patent`` także ``jezyk``) — wartość jest zawsze ta
sama (np. ``Charakter_Formalny`` o skrócie ``PAT``), więc modele pobierają ją
zapytaniem do słownika i zapamiętują na poziomie modułu.

Dawniej robiły to przez ``objects.get(...)`` + ``cached_property``: brak
wiersza w słowniku (usunięty, przemianowany skrót, świeża baza bez migracji
danych) kończył się ``DoesNotExist`` — czyli błędem 500 na całej liście
w API (``/api/v1/patent/``, ``/api/v1/praca_doktorska/``) i na stronach
rekordów. Teraz brak daje ``None`` (API: ``null``, szablony: pusto) plus
ostrzeżenie w logu, a do cache trafia WYŁĄCZNIE znaleziony obiekt — gdy wpis
się pojawi, zostanie użyty bez restartu procesu.
"""

import functools
import logging

logger = logging.getLogger(__name__)


def wpis_slownika(model, **lookup):
    """Pierwszy wpis ``model`` pasujący do ``lookup`` albo ``None`` (+ log)."""
    obj = model.objects.filter(**lookup).first()
    if obj is None:
        logger.warning(
            "Brak wpisu słownika %s (%s) — wartość pola będzie pusta.",
            model._meta.label,
            ", ".join(f"{k}={v!r}" for k, v in lookup.items()),
        )
    return obj


class cached_if_found:
    """Jak ``functools.cached_property``, ale nie zapamiętuje ``None``.

    Wynik trafia do ``instance.__dict__`` pod nazwą metody (tak samo jak
    w ``cached_property``), więc kod/testy czyszczące cache przez
    ``__dict__.pop(nazwa, None)`` działają bez zmian.
    """

    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        functools.update_wrapper(self, func)

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        value = self.func(instance)
        if value is not None:
            instance.__dict__[self.name] = value
        return value
