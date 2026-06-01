"""Generator Autorow + Autor_Jednostka."""

from __future__ import annotations

import random
from collections.abc import Iterable

from django.utils.text import slugify

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.names import IMIONA_POL, NAZWISKA_POL
from bpp.demo_data.progress import make_progress
from bpp.models import Autor, Autor_Jednostka, Jednostka


def _make_sort_key(nazwisko: str, imiona: str) -> str:
    """Zgodnie z Autor.save() — sort = nazwisko bez 'von ' + imiona, lower."""
    return (nazwisko.lower().replace("von ", "") + imiona).lower()


def create_autorzy(
    *,
    n: int,
    jednostki: Iterable[Jednostka],
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Autor]:
    """Tworzy n Autorow, kazdy pinniety do 1 losowej Jednostki przez
    Autor_Jednostka."""
    jednostki = list(jednostki)
    if not jednostki:
        raise ValueError("Brak Jednostek do podpiecia Autorow.")

    autorzy_objs: list[Autor] = []
    for i in range(n):
        imiona = rng.choice(IMIONA_POL)
        nazwisko = rng.choice(NAZWISKA_POL)
        # AutoSlugField.populate_from="get_full_name" + bulk_create:
        # find_unique() nie widzi instancji ze swojego batcha (sa jeszcze
        # nieinsertowane), wiec dwa Autorzy z identycznym (imiona, nazwisko)
        # dostaja ten sam slug → IntegrityError przy drugim INSERT.
        # Pula 87×100=8700 kombo + birthday paradox → przy --autorow 500
        # kolizja praktycznie pewna. Fix: pre-set slug z disambiguatorem
        # per-instancja. AutoSlugField pomija non-empty slug w pre_save.
        slug_value = slugify(f"{imiona} {nazwisko}-demo-{i + 1}")
        autorzy_objs.append(
            Autor(
                imiona=imiona,
                nazwisko=nazwisko,
                # Autor.save() ustawia 'sort' — bulk_create omija save(),
                # wiec ustawiamy recznie (pole TextField, NOT NULL).
                sort=_make_sort_key(nazwisko, imiona),
                slug=slug_value,
            )
        )

    pbar_a = make_progress(
        range(0, n, batch_size),
        desc="Autorzy",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Autor] = []
    for start in pbar_a:
        chunk = autorzy_objs[start : start + batch_size]
        Autor.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Autor", [a.pk for a in chunk])
        manifest.save()

    # Autor_Jednostka: pola rok_min/rok_max NIE istnieja — model uzywa
    # DateField rozpoczal_prace/zakonczyl_prace (oba nullable). Zostawiamy
    # None, zeby afiliacja byla traktowana jako "otwarta" (bez ram czasowych).
    # Constraint unique_together = (autor, jednostka, rozpoczal_prace)
    # nie kolizuje: kazdy autor dostaje wlasny rekord (1 AJ na autora).
    aj_objs = [
        Autor_Jednostka(
            autor=a,
            jednostka=rng.choice(jednostki),
        )
        for a in created
    ]

    pbar_aj = make_progress(
        range(0, len(aj_objs), batch_size),
        desc="Autor_Jednostka",
        total=(len(aj_objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar_aj:
        chunk = aj_objs[start : start + batch_size]
        Autor_Jednostka.objects.bulk_create(chunk)
        manifest.append("bpp.Autor_Jednostka", [aj.pk for aj in chunk])
        manifest.save()

    return created
