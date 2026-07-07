"""Generator wydzialow (jednostki top-level MPTT — wymaga rebuild po bulk_create)."""

from __future__ import annotations

import random

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, wydzial_nazwy
from bpp.models import Jednostka, RodzajJednostki, Uczelnia


def create_wydzialy(
    *,
    n: int,
    uczelnia: Uczelnia,
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Jednostka]:
    """Faza C (#438): „wydział" = jednostka TOP-LEVEL (``parent=None``).

    Tworzy ``n`` rootów MPTT o rodzaju „Wydział". MPTT po ``bulk_create``
    wymaga ``rebuild()`` — pola drzewa są NOT NULL (bez defaultu), więc
    ustawiamy tymczasowe 0, a ``rebuild()`` liczy poprawne lft/rght/tree_id.
    """
    rodzaj_wydzial, _ = RodzajJednostki.objects.get_or_create(nazwa="Wydział")
    nazwy = wydzial_nazwy(theme, rng, n)
    objs = [
        Jednostka(
            uczelnia=uczelnia,
            parent=None,
            nazwa=apply_prefix(nazwy[i], prefix),
            skrot=f"DW{i + 1}",
            skrot_nazwy=f"DW{i + 1}",
            rodzaj=rodzaj_wydzial,
            kolejnosc=i,
            lft=0,
            rght=0,
            tree_id=0,
            level=0,
        )
        for i in range(n)
    ]

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Wydziały",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Jednostka] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Jednostka.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Jednostka", [w.pk for w in chunk])
        manifest.save()

    Jednostka.objects.rebuild()

    return created
