"""Generator Wydawcow."""

from __future__ import annotations

import random

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Wydawca


def create_wydawcy(
    *,
    n: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawca]:
    """Tworzy n Wydawcow z prefixem 'Demo —'.

    Wydawca dziedziczy z ModelZNazwa (nazwa unique=True). Brak AutoSlugField,
    wiec wystarcza unikalna nazwa per i — bez pre-setowania slug-a.
    """
    objs = [Wydawca(nazwa=f"Demo — Wydawca {i + 1}") for i in range(n)]

    pbar = make_progress(
        range(0, n, batch_size),
        desc="Wydawcy",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydawca] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Wydawca.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawca", [w.pk for w in chunk])
        manifest.save()
    return created
