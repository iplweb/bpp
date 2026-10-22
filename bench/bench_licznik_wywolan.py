#!/usr/bin/env python
"""Policz, ile RAZY na jeden request admina powstaje ChangeList i lookupy filtra.

Atrybucja (``bench_atrybucja.py``) pokazała 504 + 504 pobrań
``Jednostka.uczelnia``, czyli enumerację wszystkich jednostek DWA razy na
request — mimo istnienia ``PerRequestChangelistInstanceMixin``, który ma
memoizować ``ChangeList`` w obrębie żądania.

Zamiast wnioskować ze stosów, liczymy wprost:

* ile razy woła się ``JednostkaFilter.lookups`` i ile razy jego generator
  faktycznie zostaje skonsumowany (to dwie różne rzeczy — ``lookups``
  zwraca generator expression, więc samo wywołanie nic nie odpytuje),
* ile razy ``get_changelist_instance`` trafia w cache, a ile razy pudłuje.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.bench")

import django  # noqa: E402

django.setup()

from bench_orm import odkryj_scenariusze  # noqa: E402

LICZNIKI = {
    "lookups_wywolan": 0,
    "lookups_skonsumowanych": 0,
    "cl_pudel": 0,
    "cl_trafien": 0,
}


def zainstaluj_liczniki():
    from bpp.admin.autor import AutorAdmin
    from bpp.admin.filters import JednostkaFilter
    from bpp.admin.xlsx_export.mixins import PerRequestChangelistInstanceMixin

    oryginalne_lookups = JednostkaFilter.lookups

    def lookups_z_licznikiem(self, request, model_admin):
        LICZNIKI["lookups_wywolan"] += 1
        wynik = oryginalne_lookups(self, request, model_admin)

        def opakowany():
            LICZNIKI["lookups_skonsumowanych"] += 1
            yield from wynik

        return opakowany()

    JednostkaFilter.lookups = lookups_z_licznikiem

    oryginalne_gci = PerRequestChangelistInstanceMixin.get_changelist_instance

    def gci_z_licznikiem(self, request):
        cache = getattr(request, "_bpp_changelist_instance_cache", None)
        if cache is not None and id(self) in cache:
            LICZNIKI["cl_trafien"] += 1
        else:
            LICZNIKI["cl_pudel"] += 1
        return oryginalne_gci(self, request)

    PerRequestChangelistInstanceMixin.get_changelist_instance = gci_z_licznikiem

    return AutorAdmin


def main():
    zainstaluj_liczniki()
    for etykieta, fn in odkryj_scenariusze():
        if etykieta != "admin: autor (changelist)":
            continue
        odp = fn()
        print(f"\n# {etykieta} (HTTP {odp.status_code})\n")
        for nazwa, ile in LICZNIKI.items():
            print(f"   {nazwa:28} {ile}")
        print(
            "\n   (504 jednostki w bazie × liczba skonsumowanych generatorów\n"
            "    = liczba pobrań Jednostka.uczelnia z filtra)"
        )
        return 0
    print("Nie znalazłem scenariusza")
    return 1


if __name__ == "__main__":
    sys.exit(main())
