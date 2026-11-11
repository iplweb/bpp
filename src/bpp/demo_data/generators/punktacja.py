"""Punktacja demo wg rozporzadzenia (zasady okresu 2022–2025).

- Czasopisma (`Zrodlo`): poziom z wykazu {20, 40, 70, 100, 140, 200}
  (`Punktacja_Zrodla` na kazdy rok demo, z rzadka ±1 prog miedzy latami)
  + `Dyscyplina_Zrodla` (1–3 dyscypliny, preferowane dyscypliny autorow
  demo). Niewielki odsetek czasopism jest spoza wykazu (brak punktacji →
  artykul dostaje 5 pkt, co kalkulator slotow przyjmuje jako „Prog3").
- Wydawcy (`Wydawca`): `Poziom_Wydawcy` II / I albo brak wpisu (spoza
  wykazu); punkty ksiazek/rozdzialow wg `PROGI_ZWARTE`.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from decimal import Decimal

from bpp.demo_data.db import bulk_create_retry
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import (
    Dyscyplina_Naukowa,
    Dyscyplina_Zrodla,
    Punktacja_Zrodla,
    Wydawca,
    Zrodlo,
)
from bpp.models.wydawca import Poziom_Wydawcy
from bpp.punktacja_sugestia import PROGI_ZWARTE

# Progi punktowe wykazu czasopism i wagi losowania (wiecej nisko/srednio
# punktowanych niz 200-tek).
PROGI_CZASOPISM: tuple[int, ...] = (20, 40, 70, 100, 140, 200)
WAGI_PROGOW_CZASOPISM: tuple[int, ...] = (25, 25, 20, 15, 10, 5)

# Procent czasopism spoza wykazu (bez Punktacja_Zrodla).
PROCENT_ZRODEL_SPOZA_WYKAZU = 5
# Szansa (w %) na zmiane progu o ±1 w danym roku wzgledem progu bazowego.
PROCENT_ZMIANY_PROGU_W_ROKU = 15
# Punkty artykulu w czasopismie spoza wykazu.
PUNKTY_SPOZA_WYKAZU = Decimal(5)

# Poziomy wydawcow: (poziom, waga). None = spoza wykazu (brak wpisu).
POZIOMY_WYDAWCOW: tuple[tuple[int | None, int], ...] = ((2, 25), (1, 45), (None, 30))

# Wariant progow dla publikacji, ktorych WSZYSCY autorzy z dyscyplina
# reprezentuja dziedziny HST — kalkulator slotow (`_dopasuj_kalkulator`)
# oczekuje wtedy podwyzszonej punktacji bazowej (monografia II: 300, I: 120;
# rozdzial II: 75; redakcja II: 150, I: 40, spoza wykazu: 10).
PROGI_ZWARTE_HST = [
    {"KS": Decimal(20), "RED": Decimal(10), "ROZ": Decimal(5)},
    {"KS": Decimal(120), "RED": Decimal(40), "ROZ": Decimal(20)},
    {"KS": Decimal(300), "RED": Decimal(150), "ROZ": Decimal(75)},
]


def _bulk_create(objs, *, model, label, desc, manifest, batch_size, disable_progress):
    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc=desc,
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar:
        chunk = objs[start : start + batch_size]
        bulk_create_retry(model.objects, chunk)
        manifest.append(label, [o.pk for o in chunk])
        manifest.save()


def _wybierz_dyscypliny_zrodla(
    rng: random.Random,
    preferowane: list[Dyscyplina_Naukowa],
    wszystkie: list[Dyscyplina_Naukowa],
) -> list[Dyscyplina_Naukowa]:
    """1–3 dyscypliny czasopisma; ~80% losowan z dyscyplin autorow demo."""
    ile = rng.randint(1, 3)
    wybrane: dict[int, Dyscyplina_Naukowa] = {}
    for _ in range(ile):
        pula = preferowane if preferowane and rng.randint(1, 100) <= 80 else wszystkie
        d = rng.choice(pula)
        wybrane[d.pk] = d
    return list(wybrane.values())


def create_punktacja_zrodel(
    *,
    zrodla: Iterable[Zrodlo],
    lata: Iterable[int],
    manifest: Manifest,
    rng: random.Random,
    dyscypliny_preferowane: Iterable[Dyscyplina_Naukowa] = (),
    batch_size: int = 500,
    disable_progress: bool = False,
) -> dict[tuple[int, int], Decimal]:
    """Tworzy Punktacja_Zrodla + Dyscyplina_Zrodla dla czasopism demo.

    Zwraca mape (zrodlo_id, rok) → punkty."""
    zrodla = list(zrodla)
    lata = list(lata)
    wszystkie = list(Dyscyplina_Naukowa.objects.all())
    preferowane = sorted(
        {d.pk: d for d in dyscypliny_preferowane}.values(), key=lambda d: d.pk
    )

    punktacje: list[Punktacja_Zrodla] = []
    dyscypliny_zrodel: list[Dyscyplina_Zrodla] = []
    mapa: dict[tuple[int, int], Decimal] = {}

    for zrodlo in zrodla:
        if rng.randint(1, 100) <= PROCENT_ZRODEL_SPOZA_WYKAZU:
            continue  # Czasopismo spoza wykazu — brak punktacji i dyscyplin.

        idx_bazowy = rng.choices(
            range(len(PROGI_CZASOPISM)), weights=WAGI_PROGOW_CZASOPISM
        )[0]
        dyscypliny = (
            _wybierz_dyscypliny_zrodla(rng, preferowane, wszystkie) if wszystkie else []
        )

        for rok in lata:
            idx = idx_bazowy
            if rng.randint(1, 100) <= PROCENT_ZMIANY_PROGU_W_ROKU:
                idx = min(max(idx + rng.choice((-1, 1)), 0), len(PROGI_CZASOPISM) - 1)
            punkty = Decimal(PROGI_CZASOPISM[idx])
            mapa[(zrodlo.pk, rok)] = punkty
            punktacje.append(
                Punktacja_Zrodla(zrodlo=zrodlo, rok=rok, punkty_kbn=punkty)
            )
            dyscypliny_zrodel.extend(
                Dyscyplina_Zrodla(zrodlo=zrodlo, rok=rok, dyscyplina=d)
                for d in dyscypliny
            )

    _bulk_create(
        punktacje,
        model=Punktacja_Zrodla,
        label="bpp.Punktacja_Zrodla",
        desc="Punktacja źródeł",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    _bulk_create(
        dyscypliny_zrodel,
        model=Dyscyplina_Zrodla,
        label="bpp.Dyscyplina_Zrodla",
        desc="Dyscypliny źródeł",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    return mapa


def create_poziomy_wydawcow(
    *,
    wydawcy: Iterable[Wydawca],
    lata: Iterable[int],
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> dict[tuple[int, int], int]:
    """Tworzy Poziom_Wydawcy (II / I / brak wpisu) per wydawca per rok.

    Poziom jest staly dla wydawcy we wszystkich latach. Zwraca mape
    (wydawca_id, rok) → poziom (tylko wydawcy z wykazu)."""
    wydawcy = list(wydawcy)
    lata = list(lata)
    poziomy = [p for p, _ in POZIOMY_WYDAWCOW]
    wagi = [w for _, w in POZIOMY_WYDAWCOW]

    objs: list[Poziom_Wydawcy] = []
    mapa: dict[tuple[int, int], int] = {}
    for wydawca in wydawcy:
        poziom = rng.choices(poziomy, weights=wagi)[0]
        if poziom is None:
            continue
        for rok in lata:
            mapa[(wydawca.pk, rok)] = poziom
            objs.append(Poziom_Wydawcy(wydawca=wydawca, rok=rok, poziom=poziom))

    _bulk_create(
        objs,
        model=Poziom_Wydawcy,
        label="bpp.Poziom_Wydawcy",
        desc="Poziomy wydawców",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    return mapa


def punktacja_zrodel_mapping(
    zrodla_ids: Iterable[int],
) -> dict[tuple[int, int], Decimal]:
    """(zrodlo_id, rok) → punkty_kbn z Punktacja_Zrodla."""
    return {
        (zid, rok): punkty
        for zid, rok, punkty in Punktacja_Zrodla.objects.filter(
            zrodlo_id__in=list(zrodla_ids)
        ).values_list("zrodlo_id", "rok", "punkty_kbn")
    }


def poziomy_wydawcow_mapping(wydawcy_ids: Iterable[int]) -> dict[tuple[int, int], int]:
    """(wydawca_id, rok) → poziom z Poziom_Wydawcy (pomija poziom NULL)."""
    return {
        (wid, rok): poziom
        for wid, rok, poziom in Poziom_Wydawcy.objects.filter(
            wydawca_id__in=list(wydawcy_ids), poziom__isnull=False
        ).values_list("wydawca_id", "rok", "poziom")
    }


def punkty_zwarte(
    *, poziom: int | None, rodzaj: str, tylko_hst: bool = False
) -> Decimal:
    """Punkty ksiazki/rozdzialu/redakcji wg progu wydawcy.

    `rodzaj`: "KS" (autorstwo monografii), "RED" (redakcja), "ROZ" (rozdzial).
    `poziom` None/-1 → spoza wykazu. `tylko_hst` → wariant HST."""
    if poziom in (None, -1):
        poziom = 0
    progi = PROGI_ZWARTE_HST if tylko_hst else PROGI_ZWARTE
    return progi[poziom][rodzaj]
