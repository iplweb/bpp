#!/usr/bin/env python
"""Benchmark ORM-a BPP: ile zapytań i ile czasu, Django 5.2 vs 6.1.

Po co: Django 6.1 wprowadziło *fetch modes*
(``QuerySet.fetch_mode(FETCH_ONE | FETCH_PEERS | FETCH_RAISE)``).
``FETCH_PEERS`` sprawia, że pierwsze leniwe dotknięcie relacji na obiekcie
z querysetu dociąga ją **hurtem dla całego rodzeństwa** z tego samego
pobrania (``prefetch_related_objects`` pod spodem), czyli zamienia N+1 na
2 zapytania — bez deklarowania ``select_related`` z góry.

Ten skrypt robi trzy rzeczy, w tej kolejności:

1. ``--inwentarz`` (tylko 6.1) — podstawia *szpiegujący* ``FetchMode``,
   który zachowuje się jak ``FETCH_ONE``, ale zapisuje każde leniwe
   pobranie: model, pole, licznik i najbliższą ramkę kodu projektu.
   To jest KROK PROFILOWANIA — inwentarz N+1 mierzony, nie zgadywany.
2. ``--pomiar`` — dla każdego scenariusza liczy zapytania (przez
   ``CaptureQueriesContext``) i czas ściany, medianą z N przebiegów.
3. ``--tryb peers`` (tylko 6.1) — to samo, ale z globalnie podstawionym
   ``FETCH_PEERS``, żeby zmierzyć SUFIT wygranej na całej aplikacji bez
   dotykania 50 miejsc w kodzie.

Uczciwość pomiaru (Gate 5 skilla python-performance):
* Ten sam Python (3.13), ta sama baza (kopia produkcji), ten sam kod
  scenariuszy — jedyna różnica to wersja Django.
* ``CACHES["default"]`` = DummyCache, więc cache aplikacji nie schowa
  pracy bazy ani po jednej, ani po drugiej stronie.
* Pierwszy przebieg każdego scenariusza jest ROZGRZEWKĄ i nie wchodzi
  do statystyki — inaczej mierzylibyśmy zimny bufor PG i import modułów.
* Raportujemy medianę i rozrzut; przy rozrzucie > 10% mediany wynik jest
  szumem i jest tak oznaczany.
"""

from __future__ import annotations

import argparse
import collections
import os
import statistics
import sys
import time
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.bench")

import django  # noqa: E402

django.setup()

from django.db import connection, reset_queries  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.urls import NoReverseMatch, reverse  # noqa: E402

WERSJA_DJANGO = django.get_version()
MA_FETCH_MODES = WERSJA_DJANGO >= "6.1"

# Skrypty leżą w ``bench/``, a kod projektu w ``src/`` — o jeden poziom wyżej.
# Ta ścieżka służy do rozpoznawania, które ramki stosu należą do BPP
# (atrybucja leniwych pobrań), więc musi wskazywać na ``<repo>/src``.
KATALOG_PROJEKTU = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)


# ---------------------------------------------------------------------------
# Szpieg leniwych pobrań (inwentarz N+1). Tylko Django >= 6.1.
# ---------------------------------------------------------------------------


def zbuduj_szpiega():
    """Zwróć ``FetchMode``, który liczy leniwe pobrania, ale ich nie blokuje.

    Dlaczego nie ``FETCH_RAISE``: on wywala się na PIERWSZYM leniwym
    pobraniu, więc jeden przebieg pokazuje jedno miejsce i chowa resztę.
    Szpieg przepuszcza pobranie dalej (``fetch_one``), więc jeden request
    wypluwa CAŁY inwentarz naraz.
    """
    from django.db.models.fetch_modes import FetchMode

    class FetchSzpieg(FetchMode):
        # Bez ``track_peers`` — udajemy dokładnie zachowanie Django 5.2.
        track_peers = False

        def __init__(self):
            self.trafienia = collections.Counter()
            self.miejsca = {}

        def fetch(self, fetcher, instance):
            klucz = (type(instance).__name__, fetcher.field.name)
            self.trafienia[klucz] += 1
            if klucz not in self.miejsca:
                self.miejsca[klucz] = _najblizsza_ramka_projektu()
            fetcher.fetch_one(instance)

    return FetchSzpieg()


def _najblizsza_ramka_projektu():
    """``plik:linia`` najgłębszej ramki należącej do kodu BPP.

    Leniwe pobranie wywołane z szablonu ma na stosie wyłącznie ramki
    Django (``template/base.py`` itd.) — wtedy zwracamy najgłębszą ramkę
    szablonową z nazwą szablonu, jeśli da się ją wyłuskać z locals.
    """
    najlepsza = None
    for ramka, linia in traceback.walk_stack(sys._getframe(2)):
        plik = ramka.f_code.co_filename
        if plik.startswith(KATALOG_PROJEKTU):
            return f"{os.path.relpath(plik, KATALOG_PROJEKTU)}:{linia}"
        if najlepsza is None and "django/template" in plik:
            szablon = _nazwa_szablonu_z_ramki(ramka)
            if szablon:
                najlepsza = f"szablon {szablon}"
    return najlepsza or "(tylko ramki Django)"


def _nazwa_szablonu_z_ramki(ramka):
    for nazwa in ("self", "context"):
        obj = ramka.f_locals.get(nazwa)
        origin = getattr(obj, "origin", None) or getattr(
            getattr(obj, "template", None), "origin", None
        )
        nazwa_szablonu = getattr(origin, "template_name", None)
        if nazwa_szablonu:
            return nazwa_szablonu
    return None


def ustaw_tryb_globalnie(tryb):
    """Podstaw ``tryb`` jako domyślny ``FetchMode`` dla CAŁEJ aplikacji.

    Dwa miejsca, bo Django czyta domyślny tryb z dwóch niezależnych
    źródeł:

    * ``query.DEFAULT_FETCH_MODE`` — czytane w ``QuerySet.__init__``, więc
      dotyczy obiektów pochodzących z querysetów (czyli praktycznie
      wszystkiego, co widzi widok),
    * ``base.FETCH_ONE`` — domyślna wartość ``ModelState.fetch_mode`` dla
      instancji powstałych POZA querysetem (``Model(...)``).

    Podstawienie ``FETCH_PEERS`` w drugim miejscu jest bezpieczne, bo
    ``ModelState.peers`` ma klasowy default ``()``, a ``FetchPeers.fetch``
    przy pustym rodzeństwie degraduje do ``fetch_one``.
    """
    from django.db.models import base as models_base
    from django.db.models import query as models_query

    models_query.DEFAULT_FETCH_MODE = tryb
    models_base.FETCH_ONE = tryb


# ---------------------------------------------------------------------------
# Scenariusze — prawdziwe requesty na prawdziwych danych.
# ---------------------------------------------------------------------------


def _url_bpp(nazwa, **kwargs):
    """``reverse`` w przestrzeni ``bpp:``, albo ``None`` gdy trasy nie ma."""
    try:
        return reverse(f"bpp:{nazwa}", kwargs=kwargs)
    except NoReverseMatch:
        return None


def _scenariusze_publiczne(klient):
    """Publiczne strony przeglądania, na identyfikatorach WZIĘTYCH Z BAZY.

    Identyfikatory z palca dałyby 404 i mierzylibyśmy obsługę błędu.
    Autora wybieramy tego z NAJWIĘKSZĄ liczbą publikacji — najostrzejszy
    przypadek dla N+1 na podstronie autora.
    """
    from django.db.models import Count

    from bpp.models import Autor, Jednostka, Rekord, Zrodlo

    autor = (
        Autor.objects.filter(pokazuj=True)
        .annotate(ile=Count("wydawnictwo_ciagle"))
        .order_by("-ile")
        .first()
    )
    jednostka = Jednostka.objects.filter(widoczna=True).first()
    zrodlo = Zrodlo.objects.first()
    rekord = Rekord.objects.exclude(rok=None).order_by("-rok").first()
    rok = rekord.rok if rekord else 2024

    pozycje = [
        ("publiczne: lista autorów", _url_bpp("browse_autorzy")),
        ("publiczne: lista jednostek", _url_bpp("browse_jednostki")),
        ("publiczne: lista źródeł", _url_bpp("browse_zrodla")),
        ("publiczne: lista lat", _url_bpp("browse_lata")),
        ("publiczne: rekordy z roku", _url_bpp("browse_rok", rok=rok)),
    ]
    if autor:
        pozycje.append(
            ("publiczne: autor (szczegóły)", _url_bpp("browse_autor", pk=autor.pk))
        )
    if jednostka:
        pozycje.append(
            (
                "publiczne: jednostka (szczegóły)",
                _url_bpp("browse_jednostka", slug=jednostka.slug),
            )
        )
    if zrodlo:
        pozycje.append(
            (
                "publiczne: źródło (szczegóły)",
                _url_bpp("browse_zrodlo", slug=zrodlo.slug),
            )
        )
    return [(e, u, klient) for e, u in pozycje]


def _klient_admina():
    """Zalogowany klient na DEDYKOWANYM koncie benchmarkowym.

    Świadomie NIE logujemy się na istniejące konto z dumpu produkcyjnego —
    to prawdziwe dane osobowe, a benchmark nie ma powodu zostawiać śladu
    w ``request.user`` cudzego konta.
    """
    from django.contrib.auth import get_user_model

    Uzytkownik = get_user_model()
    konto, _ = Uzytkownik.objects.get_or_create(
        username="__bench_admin__",
        defaults={"is_staff": True, "is_superuser": True, "is_active": True},
    )
    if not (konto.is_staff and konto.is_superuser):
        konto.is_staff = konto.is_superuser = True
        konto.save()

    klient = Client()
    klient.force_login(konto)
    return klient


def _scenariusze_z_nazw_tras(pary, klient):
    """``(etykieta, nazwa_trasy)`` → pozycje scenariuszy, pomijając brakujące."""
    pozycje = []
    for etykieta, nazwa in pary:
        try:
            pozycje.append((etykieta, reverse(nazwa), klient))
        except NoReverseMatch:
            continue
    return pozycje


def odkryj_scenariusze():
    """Zbuduj listę ``(etykieta, callable)`` z danych, które SĄ w bazie."""
    anonim = Client()
    admin = _klient_admina()

    pozycje = [
        *_scenariusze_publiczne(anonim),
        # changelisty admina to klasyczne siedlisko N+1 (list_display po FK)
        *_scenariusze_z_nazw_tras(
            (
                (
                    "admin: wyd. ciągłe (changelist)",
                    "admin:bpp_wydawnictwo_ciagle_changelist",
                ),
                (
                    "admin: wyd. zwarte (changelist)",
                    "admin:bpp_wydawnictwo_zwarte_changelist",
                ),
                ("admin: autor (changelist)", "admin:bpp_autor_changelist"),
                ("admin: źródło (changelist)", "admin:bpp_zrodlo_changelist"),
                ("admin: jednostka (changelist)", "admin:bpp_jednostka_changelist"),
            ),
            admin,
        ),
        # REST API: serializery DRF chodzą po FK per obiekt
        *_scenariusze_z_nazw_tras(
            (
                ("api_v1: rekordy", "api_v1:rekord-list"),
                ("api_v1: autorzy", "api_v1:autor-list"),
                ("api_v1: źródła", "api_v1:zrodlo-list"),
            ),
            anonim,
        ),
    ]

    return [
        (etykieta, lambda u=url, k=klient: k.get(u))
        for etykieta, url, klient in pozycje
        if url
    ]


# ---------------------------------------------------------------------------
# Pomiar
# ---------------------------------------------------------------------------


def zmierz(fn, powtorzenia):
    """Zwróć ``(mediana_ms, rozrzut_ms, zapytania, kod_http)``.

    Pierwszy przebieg to rozgrzewka — odrzucany. Bez tego mierzylibyśmy
    zimne bufory PostgreSQL i leniwe importy Django, a nie pracę ORM-a.
    """
    odpowiedz = fn()
    kod = getattr(odpowiedz, "status_code", None)

    reset_queries()
    with CaptureQueriesContext(connection) as ctx:
        fn()
    zapytania = len(ctx.captured_queries)

    czasy = []
    for _ in range(powtorzenia):
        start = time.perf_counter()
        fn()
        czasy.append((time.perf_counter() - start) * 1000)

    mediana = statistics.median(czasy)
    rozrzut = statistics.stdev(czasy) if len(czasy) > 1 else 0.0
    return mediana, rozrzut, zapytania, kod


def uruchom_pomiar(powtorzenia, tryb):
    if tryb == "peers":
        if not MA_FETCH_MODES:
            sys.exit("--tryb peers wymaga Django >= 6.1")
        from django.db.models import FETCH_PEERS

        ustaw_tryb_globalnie(FETCH_PEERS)

    scenariusze = odkryj_scenariusze()
    print(f"\n# Django {WERSJA_DJANGO}, tryb={tryb}, powtórzeń={powtorzenia}\n")
    print(
        f"{'scenariusz':38} {'zapytań':>8} {'ms (mediana)':>13} {'±ms':>7} {'HTTP':>5}"
    )
    print("-" * 76)
    wyniki = {}
    for etykieta, fn in scenariusze:
        try:
            mediana, rozrzut, zapytania, kod = zmierz(fn, powtorzenia)
        except Exception as exc:  # noqa: BLE001 - raportujemy i lecimy dalej
            print(f"{etykieta:38} {'BŁĄD':>8}  {type(exc).__name__}: {exc}"[:120])
            continue
        flaga = "  SZUM" if mediana and rozrzut > 0.10 * mediana else ""
        print(
            f"{etykieta:38} {zapytania:>8} {mediana:>13.1f} {rozrzut:>7.1f} "
            f"{kod:>5}{flaga}"
        )
        wyniki[etykieta] = {"zapytania": zapytania, "ms": mediana, "http": kod}
    return wyniki


def uruchom_inwentarz():
    if not MA_FETCH_MODES:
        sys.exit("--inwentarz wymaga Django >= 6.1 (fetch modes)")

    szpieg = zbuduj_szpiega()
    ustaw_tryb_globalnie(szpieg)

    scenariusze = odkryj_scenariusze()
    print(f"\n# INWENTARZ leniwych pobrań — Django {WERSJA_DJANGO}\n")
    for etykieta, fn in scenariusze:
        szpieg.trafienia.clear()
        szpieg.miejsca.clear()
        try:
            odpowiedz = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"\n## {etykieta}\n   BŁĄD: {type(exc).__name__}: {exc}"[:200])
            continue
        kod = getattr(odpowiedz, "status_code", "?")
        suma = sum(szpieg.trafienia.values())
        print(f"\n## {etykieta}  (HTTP {kod}) — leniwych pobrań: {suma}")
        if not suma:
            print(
                "   (brak — wszystko przez select_related/prefetch albo kolumny lokalne)"
            )
            continue
        for (model, pole), ile in szpieg.trafienia.most_common(12):
            print(f"   {ile:>6}×  {model}.{pole:<28} @ {szpieg.miejsca[(model, pole)]}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inwentarz", action="store_true", help="wykryj miejsca N+1 (6.1)")
    p.add_argument("--pomiar", action="store_true", help="zmierz zapytania i czas")
    p.add_argument("--tryb", choices=("one", "peers"), default="one")
    p.add_argument("--powtorzenia", type=int, default=5)
    args = p.parse_args()

    if not (args.inwentarz or args.pomiar):
        p.error("podaj --inwentarz albo --pomiar")
    if args.inwentarz:
        uruchom_inwentarz()
    if args.pomiar:
        uruchom_pomiar(args.powtorzenia, args.tryb)


if __name__ == "__main__":
    main()
