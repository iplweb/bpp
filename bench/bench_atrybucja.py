#!/usr/bin/env python
"""Rozbij leniwe pobrania JEDNEGO pola na konkretne miejsca w kodzie.

``bench_orm.py --inwentarz`` pokazuje pierwsze miejsce dla danej pary
(model, pole). Gdy licznik nie zgadza się z liczbą wierszy na stronie
(np. 1058 pobrań ``Jednostka.uczelnia`` przy 504 jednostkach w bazie),
trzeba wiedzieć, ILE pobrań przychodzi z KTÓREJ ścieżki wywołania — bo
inaczej opowiadamy o mechanizmie, którego nie sprawdziliśmy.

Ten skrypt liczy pobrania per *podpis stosu* zredukowany do ramek kodu
projektu — czyli „kto to wywołał", a nie tylko „gdzie pękło".

Użycie::

    uv run python bench_atrybucja.py [Model.pole] [etykieta scenariusza]

Domyślnie ``Jednostka.uczelnia`` na ``admin: autor (changelist)``. Działa
zarówno dla relacji (``fetcher`` = deskryptor FK), jak i dla pól
odroczonych (``fetcher`` = ``DeferredAttribute``) — oba mają ``.field``.
"""

from __future__ import annotations

import collections
import os
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.bench")

import django  # noqa: E402

django.setup()

from bench_orm import (  # noqa: E402
    KATALOG_PROJEKTU,
    odkryj_scenariusze,
    ustaw_tryb_globalnie,
)
from django.db.models.fetch_modes import FetchMode  # noqa: E402

CEL = tuple((sys.argv[1] if len(sys.argv) > 1 else "Jednostka.uczelnia").split("."))
SCENARIUSZ = sys.argv[2] if len(sys.argv) > 2 else "admin: autor (changelist)"


def podpis_stosu(pomin=3, ile_ramek=4):
    """Do ``ile_ramek`` najgłębszych ramek kodu projektu, od najgłębszej."""
    ramki = []
    for ramka, linia in traceback.walk_stack(sys._getframe(pomin)):
        plik = ramka.f_code.co_filename
        if plik.startswith(KATALOG_PROJEKTU):
            ramki.append(
                f"{os.path.relpath(plik, KATALOG_PROJEKTU)}:{linia}"
                f" ({ramka.f_code.co_name})"
            )
            if len(ramki) >= ile_ramek:
                break
    return " ← ".join(ramki) or "(brak ramek projektu)"


class FetchAtrybucja(FetchMode):
    track_peers = False

    def __init__(self):
        self.per_stos = collections.Counter()
        self.suma = 0

    def fetch(self, fetcher, instance):
        if (type(instance).__name__, fetcher.field.name) == CEL:
            self.suma += 1
            self.per_stos[podpis_stosu()] += 1
        fetcher.fetch_one(instance)


def main():
    szpieg = FetchAtrybucja()
    ustaw_tryb_globalnie(szpieg)

    for etykieta, fn in odkryj_scenariusze():
        if etykieta != SCENARIUSZ:
            continue
        odp = fn()
        print(f"\n# {SCENARIUSZ} (HTTP {odp.status_code})")
        print(f"# leniwych pobrań {CEL[0]}.{CEL[1]}: {szpieg.suma}\n")
        for stos, ile in szpieg.per_stos.most_common(10):
            print(f"{ile:>6}×  {stos}")
        return 0
    print(f"Nie znalazłem scenariusza {SCENARIUSZ!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
