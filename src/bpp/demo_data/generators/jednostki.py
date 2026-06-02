"""Generator Jednostek (MPTT model — wymaga rebuild po bulk_create)."""

from __future__ import annotations

import random
from collections.abc import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, compose_jednostka_nazwa
from bpp.models import Jednostka, Uczelnia, Wydzial


def create_jednostki(
    *,
    per_wydzial: int,
    wydzialy: Iterable[Wydzial],
    uczelnia: Uczelnia,
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Jednostka]:
    wydzialy = list(wydzialy)
    objs: list[Jednostka] = []
    for w_idx, wydzial in enumerate(wydzialy, start=1):
        for j_idx in range(1, per_wydzial + 1):
            objs.append(
                Jednostka(
                    uczelnia=uczelnia,
                    wydzial=wydzial,
                    nazwa=apply_prefix(compose_jednostka_nazwa(theme, rng), prefix),
                    skrot=f"DJ{w_idx}-{j_idx}",
                    rodzaj_jednostki=Jednostka.RODZAJ_JEDNOSTKI.NORMALNA,
                    # MPTT NOT NULL fields — wartosci tymczasowe; rebuild()
                    # ponizej ustawia poprawne lft/rght/tree_id/level.
                    lft=0,
                    rght=0,
                    tree_id=0,
                    level=0,
                )
            )

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Jednostki",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Jednostka] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Jednostka.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Jednostka", [j.pk for j in chunk])
        manifest.save()

    Jednostka.objects.rebuild()

    return created
