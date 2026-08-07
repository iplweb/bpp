#!/usr/bin/env python
"""Sprawdź, czy ``FETCH_PEERS`` NIE zmienia tego, co strona zwraca.

Sam spadek liczby zapytań nic nie znaczy, dopóki nie wiadomo, że wynik
jest ten sam — „szybciej, ale inaczej" to nie optymalizacja, to regresja.
Dlatego dla każdego scenariusza pobieramy odpowiedź DWA razy w tym samym
procesie: raz w ``FETCH_ONE`` (zachowanie Django 5.2), raz w
``FETCH_PEERS`` — i porównujemy bajt w bajt.

Kolejność jest ustalona (ONE, potem PEERS) i sprawdzamy też ONE↔ONE, żeby
odsiać strony niedeterministyczne z natury (CSRF token, znacznik czasu,
losowa kolejność) — inaczej ich niestabilność wyglądałaby jak wina
``FETCH_PEERS``.
"""

from __future__ import annotations

import os
import re
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.bench")

import django  # noqa: E402

django.setup()

from bench_orm import odkryj_scenariusze, ustaw_tryb_globalnie  # noqa: E402
from django.db.models import FETCH_ONE, FETCH_PEERS  # noqa: E402

# Elementy zmienne PER REQUEST, niezależne od trybu pobierania. Każdy z nich
# został wskazany empirycznie — porównaniem dwóch odpowiedzi w tym SAMYM
# trybie (FETCH_ONE↔FETCH_ONE), więc żaden nie maskuje różnicy, którą mógłby
# wprowadzić FETCH_PEERS. Bez tej normalizacji strony admina są nieporównywalne.
WZORCE_ZMIENNE = [
    # token CSRF: pole formularza, nagłówek XHR, querystring, literał JS
    (re.compile(rb'name="csrfmiddlewaretoken" value="[^"]*"'), b"CSRF-POLE"),
    (re.compile(rb'X-CSRFToken", "[^"]*"'), b"CSRF-XHR"),
    (re.compile(rb"csrfmiddlewaretoken=[A-Za-z0-9]+"), b"CSRF-QS"),
    (re.compile(rb"csrfmiddlewaretoken: '[^']*'"), b"CSRF-JS"),
    # znacznik czasu generacji strony w stopce BPP
    (re.compile(rb"wygenerowano dnia [^,]+,"), b"CZAS,"),
]


def znormalizuj(tresc):
    for wzorzec, zamiennik in WZORCE_ZMIENNE:
        tresc = wzorzec.sub(zamiennik, tresc)
    return tresc


def pobierz(fn, tryb):
    ustaw_tryb_globalnie(tryb)
    odp = fn()
    return getattr(odp, "status_code", None), znormalizuj(getattr(odp, "content", b""))


def main():
    scenariusze = odkryj_scenariusze()
    print(
        f"\n# RÓWNOWAŻNOŚĆ wyniku: FETCH_ONE vs FETCH_PEERS (Django {django.get_version()})\n"
    )
    print(f"{'scenariusz':38} {'HTTP':>5} {'bajtów':>9}  wynik")
    print("-" * 84)

    ilezle = 0
    for etykieta, fn in scenariusze:
        try:
            kod_a, tresc_a = pobierz(fn, FETCH_ONE)
            kod_a2, tresc_a2 = pobierz(fn, FETCH_ONE)
            kod_b, tresc_b = pobierz(fn, FETCH_PEERS)
        except Exception as exc:  # noqa: BLE001 - raportujemy i lecimy dalej
            print(
                f"{etykieta:38} {'—':>5} {'—':>9}  BŁĄD {type(exc).__name__}: {exc}"[
                    :150
                ]
            )
            ilezle += 1
            continue

        stabilna = tresc_a == tresc_a2
        zgodna = tresc_a == tresc_b

        if not stabilna:
            # Strona sama z siebie nie jest deterministyczna — porównanie
            # z PEERS nic nie powie. Porównujemy wtedy tylko długość i kod.
            werdykt = (
                "NIEDETERMINISTYCZNA (ONE≠ONE); "
                f"dł. ONE={len(tresc_a)} PEERS={len(tresc_b)}, HTTP zgodny={kod_a == kod_b}"
            )
        elif zgodna and kod_a == kod_b:
            werdykt = "OK — identyczna"
        else:
            werdykt = (
                f"!! ROZJECHANA (HTTP {kod_a}→{kod_b}, {len(tresc_a)}→{len(tresc_b)} B)"
            )
            ilezle += 1

        print(f"{etykieta:38} {kod_a!s:>5} {len(tresc_a):>9}  {werdykt}")

    print()
    if ilezle:
        print(f"UWAGA: {ilezle} scenariusz(y) NIE potwierdziło równoważności.")
        return 1
    print("Wszystkie deterministyczne scenariusze: wynik identyczny w obu trybach.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
