"""Generator Zrodel (czasopism)."""

from __future__ import annotations

import random

from django.utils.text import slugify

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Rodzaj_Zrodla, Zrodlo


def _synthetic_issn(rng: random.Random) -> str:
    """Generuje syntetyczny ISSN w formacie NNNN-NNNN (ostatnia cyfra:
    random digit lub 'X')."""
    first = "".join(str(rng.randint(0, 9)) for _ in range(4))
    second = "".join(str(rng.randint(0, 9)) for _ in range(3))
    last = rng.choice("0123456789X")
    return f"{first}-{second}{last}"


def create_zrodla(
    *,
    n: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Zrodlo]:
    """Tworzy n Zrodel z syntetycznym ISSN i losowym Rodzaj_Zrodla."""
    rodzaje = list(Rodzaj_Zrodla.objects.all())
    if not rodzaje:
        raise ValueError("Brak Rodzaj_Zrodla w bazie.")

    objs: list[Zrodlo] = []
    for i in range(n):
        nazwa = f"Demo — Czasopismo {i + 1}"
        # Zrodlo.slug = AutoSlugField(populate_from="nazwa", unique=True).
        # bulk_create + find_unique() nie widzi siostr w batchu, wiec
        # pre-setujemy slug z disambiguatorem per-instancja. AutoSlugField
        # pomija non-empty slug w pre_save. Patrz analogiczny fix w autorzy.py.
        objs.append(
            Zrodlo(
                nazwa=nazwa,
                skrot=f"DC{i + 1}",
                rodzaj=rng.choice(rodzaje),
                issn=_synthetic_issn(rng),
                slug=slugify(f"{nazwa}-demo-{i + 1}"),
            )
        )

    pbar = make_progress(
        range(0, n, batch_size),
        desc="Źródła",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Zrodlo] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Zrodlo.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Zrodlo", [z.pk for z in chunk])
        manifest.save()
    return created
