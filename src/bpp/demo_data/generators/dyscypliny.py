"""Generator Autor_Dyscyplina per autor per rok."""

from __future__ import annotations

import random
from collections.abc import Iterable

from bpp.demo_data.db import bulk_create_retry
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa

ROK_ZMIANY = 2022


def create_autor_dyscypliny(
    *,
    autorzy: Iterable[Autor],
    lata: Iterable[int],
    procent_z_dyscyplina: int,
    procent_z_subdyscyplina: int,
    procent_zmiana_dyscypliny: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Autor_Dyscyplina]:
    """Tworzy Autor_Dyscyplina per (autor, rok) wg procentow z CLI."""
    autorzy = list(autorzy)
    lata = list(lata)
    dyscypliny = list(Dyscyplina_Naukowa.objects.all())
    if not dyscypliny:
        raise ValueError("Brak Dyscyplin_Naukowych w bazie.")

    # Per autor: czy ma dyscypline, czy ma subdyscypline, czy zmienia w 2022.
    # Wszystkie procenty 0–100 (jezeli 100 → wszyscy, jezeli 0 → nikt).
    objs: list[Autor_Dyscyplina] = []
    for autor in autorzy:
        if rng.randint(1, 100) > procent_z_dyscyplina:
            continue

        zmienia = rng.randint(1, 100) <= procent_zmiana_dyscypliny
        ma_subdyscypline = rng.randint(1, 100) <= procent_z_subdyscyplina

        d_pre = rng.choice(dyscypliny)
        d_post = (
            rng.choice([d for d in dyscypliny if d.pk != d_pre.pk])
            if zmienia and len(dyscypliny) > 1
            else d_pre
        )

        for rok in lata:
            dyscyplina = d_post if rok >= ROK_ZMIANY else d_pre
            subdyscyplina = None
            if ma_subdyscypline and len(dyscypliny) > 1:
                candidates = [d for d in dyscypliny if d.pk != dyscyplina.pk]
                subdyscyplina = rng.choice(candidates)

            objs.append(
                Autor_Dyscyplina(
                    autor=autor,
                    rok=rok,
                    dyscyplina_naukowa=dyscyplina,
                    subdyscyplina_naukowa=subdyscyplina,
                    procent_dyscypliny=100,
                    wymiar_etatu=1,
                )
            )

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Autor_Dyscyplina",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Autor_Dyscyplina] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        bulk_create_retry(Autor_Dyscyplina.objects, chunk)
        created.extend(chunk)
        manifest.append("bpp.Autor_Dyscyplina", [ad.pk for ad in chunk])
        manifest.save()

    return created
