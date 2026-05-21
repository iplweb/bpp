"""Generator Wydzialow."""

from __future__ import annotations

import random

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.names import KIERUNKI_POL
from bpp.demo_data.progress import make_progress
from bpp.models import Uczelnia, Wydzial


def create_wydzialy(
    *,
    n: int,
    uczelnia: Uczelnia,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydzial]:
    created: list[Wydzial] = []
    kierunki = list(KIERUNKI_POL)
    rng.shuffle(kierunki)
    kierunki = (kierunki * ((n // len(kierunki)) + 1))[:n]

    objs = [
        Wydzial(
            uczelnia=uczelnia,
            nazwa=f"Demo — Wydział {i + 1} ({kierunki[i]})",
            skrot=f"DW{i + 1}",
            skrot_nazwy=f"Demo W{i + 1}",
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
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Wydzial.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydzial", [w.pk for w in chunk])
        manifest.save()

    return created
