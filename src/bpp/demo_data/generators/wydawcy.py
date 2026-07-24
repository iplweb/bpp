"""Generator Wydawcow."""

from __future__ import annotations

import random

from bpp.demo_data.db import bulk_create_retry
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, wydawca_nazwy
from bpp.models import Wydawca


def create_wydawcy(
    *,
    n: int,
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawca]:
    """Tworzy n Wydawcow z nazwami z motywu.

    Wydawca dziedziczy z ModelZNazwa (nazwa unique=True). Unikalnosc
    zapewnia wydawca_nazwy() przez cyklowanie z przyrostkiem oddzialu.
    """
    nazwy = wydawca_nazwy(theme, rng, n)
    objs = [Wydawca(nazwa=apply_prefix(nazwy[i], prefix)) for i in range(n)]

    pbar = make_progress(
        range(0, n, batch_size),
        desc="Wydawcy",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydawca] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        bulk_create_retry(Wydawca.objects, chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawca", [w.pk for w in chunk])
        manifest.save()
    return created
