"""Generator Autor_Dyscyplina per autor per rok.

Kazdy autor z dyscyplina dostaje JEDEN rodzaj autora (wspolny dla wszystkich
lat): ~60% „N" (w liczbie N), ~30% „B" (badawczy spoza N), ~10% „D"
(doktorant). Wymiar etatu 1 i 100% dyscypliny wiodacej (subdyscyplina bez
procentu) daja `Autor_Dyscyplina.policz_udzialy()` == 1 udzial na rok — czyli
~1 slot do wypelnienia na rok (4 na okres 2022–2025, gorny limit
`oblicz_sumy_udzialow_za_calosc`).
"""

from __future__ import annotations

import random
from collections.abc import Iterable

from bpp.demo_data.db import bulk_create_retry
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa

ROK_ZMIANY = 2022

# (skrot Rodzaj_Autora, prog skumulowany w %): N 60%, B 30%, D 10%.
ROZKLAD_RODZAJOW_AUTORA: tuple[tuple[str, int], ...] = (
    ("N", 60),
    ("B", 90),
    ("D", 100),
)


def _wczytaj_rodzaje_autora() -> dict:
    """Mapa skrot → Rodzaj_Autora dla skrotow z ROZKLAD_RODZAJOW_AUTORA.

    Brak slownika (np. pusta baza testowa) → pusta mapa; wtedy rodzaj_autora
    zostaje NULL (jak przed rozszerzeniem generatora)."""
    from ewaluacja_common.models import Rodzaj_Autora

    skroty = [skrot for skrot, _ in ROZKLAD_RODZAJOW_AUTORA]
    return {ra.skrot: ra for ra in Rodzaj_Autora.objects.filter(skrot__in=skroty)}


def _losuj_rodzaj_autora(rng: random.Random, rodzaje: dict):
    los = rng.randint(1, 100)
    for skrot, prog in ROZKLAD_RODZAJOW_AUTORA:
        if los <= prog:
            return rodzaje.get(skrot)
    return None


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
    rodzaje_autora = _wczytaj_rodzaje_autora()

    # Per autor: czy ma dyscypline, czy ma subdyscypline, czy zmienia w 2022.
    # Wszystkie procenty 0–100 (jezeli 100 → wszyscy, jezeli 0 → nikt).
    objs: list[Autor_Dyscyplina] = []
    for autor in autorzy:
        if rng.randint(1, 100) > procent_z_dyscyplina:
            continue

        zmienia = rng.randint(1, 100) <= procent_zmiana_dyscypliny
        ma_subdyscypline = rng.randint(1, 100) <= procent_z_subdyscyplina
        rodzaj_autora = _losuj_rodzaj_autora(rng, rodzaje_autora)

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
                    rodzaj_autora=rodzaj_autora,
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
