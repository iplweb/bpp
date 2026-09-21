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
    (
        "bpp.migrations.0464_rodzajjednostki_autor_moze_afiliowac",
        "wydzial_bez_afiliacji",
    ),
]


#: Migracja ``0480`` mapuje skrót języka na kod BCP 47 — reużywamy jej
#: mapowania i funkcji, zamiast przepisywać kody tutaj.
MODUL_KODY_JEZYKOW = "bpp.migrations.0480_cerif_mapowania_slownikow"

#: ``pol.`` i ``ang.`` tworzy migracja ``0022``, ale z ``assert pk == 1/2`` —
#: po ``TRUNCATE`` sekwencje bywają inne, więc zamiast jej wołać powtarzamy
#: tu sam klucz naturalny (skrót) i nazwę. Reszta języków jedzie z fixture.
JEZYKI_BAZOWE = {"pol.": "polski", "ang.": "angielski"}


def seed_rodzaje_jednostek():
    from django.apps import apps as django_apps

    for modul, funkcja in SEED_RODZAJE_JEDNOSTEK:
        getattr(import_module(modul), funkcja)(django_apps, None)


def seed_jezyki():
    """Odtwórz ``Jezyk`` — w tym ``kod_bcp47``, po którym importer dobiera
    język pracy (``importer_publikacji``).

    Migracja ``0035`` wgrywa języki z fixture ``jezyk.json`` przez ``create``,
    więc po flushu nie da się jej powtórzyć. Bierzemy więc ten sam fixture,
    ale ``get_or_create`` po skrócie (klucz naturalny), a kody BCP 47 dokłada
    idempotentne ``_uzupelnij`` z migracji ``0480``.

    Czego tu NIE ma: ``skrot_crossref``. Kolumna jest ``unique``, a w bazie
    produkcyjnej wypełnia ją wyłącznie migracja ``0410`` i tylko dla polskiego
    — ustawianie jej tutaj (receiver leci po KAŻDYM ``migrate``) mogłoby wejść
    w konflikt z wartością nadaną przez redakcję. Testom, które potrzebują
    ``skrot_crossref``, dokłada go fixture ``jezyki``.
    """
    from django.apps import apps as django_apps

    from bpp.util import get_fixture

    Jezyk = django_apps.get_model("bpp", "Jezyk")
    for skrot, nazwa in JEZYKI_BAZOWE.items():
        Jezyk.objects.get_or_create(skrot=skrot, defaults={"nazwa": nazwa})

    for pola in get_fixture("jezyk").values():
        pola = dict(pola)
        Jezyk.objects.get_or_create(skrot=pola.pop("skrot"), defaults=pola)

    kody = import_module(MODUL_KODY_JEZYKOW)
    kody._uzupelnij(Jezyk, "kod_bcp47", kody.JEZYKI)


def seed_slowniki(sender, **kwargs):
    """Receiver ``post_migrate`` — odtwarza słowniki po flushu/migracji.

    ``sender`` to AppConfig; wołane raz per app — filtrujemy do ``bpp``.
    ``flush`` nie przekazuje ``apps`` w kwargs, a po ``post_migrate`` rejestr
    modeli jest gotowy — więc wołane funkcje biorą ``django.apps.apps``.
    """
    if getattr(sender, "name", None) != "bpp":
        return
    seed_rodzaje_jednostek()
    seed_jezyki()
