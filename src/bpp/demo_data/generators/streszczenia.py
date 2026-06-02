"""Generator streszczeń (Wydawnictwo_Ciagle/Zwarte_Streszczenie)."""

from __future__ import annotations

import random
from collections.abc import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import compose_streszczenie
from bpp.models import (
    Jezyk,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Streszczenie,
)


def _jezyk_polski() -> Jezyk | None:
    """Kanoniczny lookup polskiego (jak bpp/models/patent.py:56), z fallback."""
    return Jezyk.objects.filter(nazwa__icontains="polski").first()


def _create_for(
    *,
    model,
    label,
    prace,
    theme,
    procent,
    jezyk,
    manifest,
    rng,
    batch_size,
    disable_progress,
):
    objs = [
        model(
            rekord=praca,
            streszczenie=compose_streszczenie(theme, rng),
            jezyk_streszczenia=jezyk,
        )
        for praca in prace
        if rng.randint(1, 100) <= procent
    ]
    if not objs:
        return
    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc=f"Streszczenia {label}",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar:
        chunk = objs[start : start + batch_size]
        model.objects.bulk_create(chunk)
        manifest.append(label, [o.pk for o in chunk])
        manifest.save()


def create_streszczenia(
    *,
    prace_wc: Iterable[Wydawnictwo_Ciagle],
    prace_wz: Iterable[Wydawnictwo_Zwarte],
    theme: Theme,
    procent: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> None:
    """Tworzy 1 streszczenie (PL) dla ~procent% prac WC i WZ."""
    if not 0 <= procent <= 100:
        raise ValueError(f"procent musi być w [0, 100], dostał {procent}")
    jezyk = _jezyk_polski()
    _create_for(
        model=Wydawnictwo_Ciagle_Streszczenie,
        label="bpp.Wydawnictwo_Ciagle_Streszczenie",
        prace=list(prace_wc),
        theme=theme,
        procent=procent,
        jezyk=jezyk,
        manifest=manifest,
        rng=rng,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    _create_for(
        model=Wydawnictwo_Zwarte_Streszczenie,
        label="bpp.Wydawnictwo_Zwarte_Streszczenie",
        prace=list(prace_wz),
        theme=theme,
        procent=procent,
        jezyk=jezyk,
        manifest=manifest,
        rng=rng,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
