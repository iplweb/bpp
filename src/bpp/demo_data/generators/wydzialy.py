"""Generator Wydzialow."""

from __future__ import annotations

import random

from bpp.demo_data.db import bulk_create_retry
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, wydzial_nazwy
from bpp.models import Uczelnia, Wydzial


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
) -> list[Wydzial]:
    nazwy = wydzial_nazwy(theme, rng, n)
    objs = [
        Wydzial(
            uczelnia=uczelnia,
            nazwa=apply_prefix(nazwy[i], prefix),
            skrot=f"DW{i + 1}",
            skrot_nazwy=f"DW{i + 1}",
            kolejnosc=i,
        )
        for i in range(n)
    ]

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Wydziały",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydzial] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        bulk_create_retry(Wydzial.objects, chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydzial", [w.pk for w in chunk])
        manifest.save()
    return created
