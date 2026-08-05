"""Idempotentny seed słowników referencyjnych — odpalany pod ``post_migrate``.

Dane słownikowe (``RodzajJednostki``, …) są seedowane migracjami danych.
Migracja odpala się RAZ, a transakcyjny flush testów
(``TransactionTestCase._fixture_teardown`` → ``TRUNCATE``) je zmiata.
``post_migrate`` emitowany po flushu (i po ``migrate``) daje pretekst, żeby je
odtworzyć — tym samym wzorcem, którym repo odtwarza grupy
(``bpp.apps.odtworz_grupy``) i raporty (``nowe_raporty`` ``seed_reports``).

Zamiast DUPLIKOWAĆ wartości (co dryfuje — stan „Wydział" pochodzi z kilku
migracji: 0449 baza, 0454 ``pokazuj_strukture_podjednostek``, 0464
``autor_moze_afiliowac``), **reużywamy oryginalnych funkcji seedujących**. Są
idempotentne (``update_or_create`` / ``filter().update()``), więc bezpieczne do
wielokrotnego odpalenia i w produkcji (po ``migrate`` no-op na zdrowej bazie).
CLAUDE.md zabrania ruszać migracje — więc pozostają jedynym źródłem prawdy, a
tu tylko je wołamy w kolejności zależności.

Sprzężenie z nazwami funkcji migracji jest świadome: repo nigdy nie modyfikuje
plików migracji, więc funkcje są stabilne. Gdyby przyszła migracja dołożyła
kolejny atrybut słownika — dopisz jej funkcję do łańcucha poniżej.
"""

from importlib import import_module

# (moduł migracji, nazwa funkcji) — w kolejności zależności. Każda idempotentna.
SEED_RODZAJE_JEDNOSTEK = [
    ("bpp.migrations.0449_seed_rodzajjednostki", "seed"),
    ("bpp.migrations.0454_faza_b_i1", "seed_pokazuj_strukture_podjednostek"),
    ("bpp.migrations.0464_rodzajjednostki_autor_moze_afiliowac", "wydzial_bez_afiliacji"),
]


def seed_rodzaje_jednostek():
    from django.apps import apps as django_apps

    for modul, funkcja in SEED_RODZAJE_JEDNOSTEK:
        getattr(import_module(modul), funkcja)(django_apps, None)


def seed_slowniki(sender, **kwargs):
    """Receiver ``post_migrate`` — odtwarza słowniki po flushu/migracji.

    ``sender`` to AppConfig; wołane raz per app — filtrujemy do ``bpp``.
    ``flush`` nie przekazuje ``apps`` w kwargs, a po ``post_migrate`` rejestr
    modeli jest gotowy — więc wołane funkcje biorą ``django.apps.apps``.
    """
    if getattr(sender, "name", None) != "bpp":
        return
    seed_rodzaje_jednostek()
