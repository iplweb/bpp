"""Generator autorów w dwóch dyscyplinach („dwudyscyplinowców").

Każdy dostaje pseudonim „dwudyscyplinowy" (widać go w nazwie autora w całym
BPP), ``Autor_Dyscyplina`` na każdy rok z podziałem 60/40 (wymiar etatu 1,
rodzaj „N" — 0,6 + 0,4 udziału) i kilka artykułów. Połowa artykułów jest
przypisana do drugiej dyscypliny (subdyscypliny) i ukazała się
w czasopiśmie, które tę dyscyplinę ma w ``Dyscyplina_Zrodla`` za dany rok —
taka praca jest „zgodna" na ekranie ``ewaluacja_dwudyscyplinowcy``.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable

from bpp.demo_data.db import bulk_create_z_manifestem
from bpp.demo_data.generators._publikacje_common import autor_dyscyplina_mapping
from bpp.demo_data.generators.autorzy import utworz_autorow
from bpp.demo_data.generators.punktacja import punktacja_zrodel_mapping
from bpp.demo_data.generators.wydawnictwa_ciagle import _build_praca, _load_slowniki
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import compose_autor
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Autor_Jednostka,
    Dyscyplina_Naukowa,
    Dyscyplina_Zrodla,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)

PSEUDONIM = "dwudyscyplinowy"
PROCENT_DYSCYPLINY = 60
PROCENT_SUBDYSCYPLINY = 40


def create_dwudyscyplinowcy(
    *,
    n: int,
    jednostki: Iterable[Jednostka],
    zrodla: Iterable[Zrodlo],
    wspolautorzy: Iterable[Autor],
    lata: Iterable[int],
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    idx_start: int,
    prace_na_autora: int = 6,
    marker: str = "",
    batch_size: int = 500,
    disable_progress: bool = False,
) -> tuple[list[Autor], list[Wydawnictwo_Ciagle]]:
    """Tworzy ``n`` dwudyscyplinowców z artykułami. Zwraca (autorzy, prace).

    ``idx_start`` — numer ostatniej pracy ciągłej demo; nowe prace dostają
    kolejne numery (tytuł „(nr N)" i slug muszą być unikalne)."""
    jednostki = list(jednostki)
    zrodla = list(zrodla)
    lata = list(lata)
    dyscypliny = [d.pk for d in Dyscyplina_Naukowa.objects.order_by("pk")]
    if n <= 0 or len(dyscypliny) < 2 or not jednostki or not zrodla or not lata:
        return [], []

    from ewaluacja_common.models import Rodzaj_Autora

    rodzaj_n = Rodzaj_Autora.objects.filter(skrot="N").first()

    # (rok, dyscyplina) -> czasopisma demo z tą dyscypliną w danym roku:
    zrodla_wg_dyscypliny: dict[tuple[int, int], list[int]] = defaultdict(list)
    for zrodlo_id, rok, dyscyplina_id in (
        Dyscyplina_Zrodla.objects.filter(zrodlo__in=zrodla)
        .order_by("pk")
        .values_list("zrodlo_id", "rok", "dyscyplina_id")
    ):
        zrodla_wg_dyscypliny[(rok, dyscyplina_id)].append(zrodlo_id)
    zrodla_po_pk = {z.pk: z for z in zrodla}
    # Druga dyscyplina — z tych, które mają czasopisma (praca może być zgodna):
    drugie = sorted({d for (_rok, d) in zrodla_wg_dyscypliny}) or dyscypliny

    dane = []
    for _ in range(n):
        imiona, nazwisko = compose_autor(theme, rng)
        dane.append((imiona, nazwisko, rng.choice(jednostki), {"pseudonim": PSEUDONIM}))
    autorzy = utworz_autorow(
        dane,
        slug_tag="dwudyscyplinowy",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
        desc="Dwudyscyplinowcy",
    )

    pary: dict[int, tuple[int, int]] = {}
    ad_objs = []
    for autor in autorzy:
        d2 = rng.choice(drugie)
        d1 = rng.choice([d for d in dyscypliny if d != d2])
        pary[autor.pk] = (d1, d2)
        for rok in lata:
            ad_objs.append(
                Autor_Dyscyplina(
                    autor=autor,
                    rok=rok,
                    dyscyplina_naukowa_id=d1,
                    subdyscyplina_naukowa_id=d2,
                    procent_dyscypliny=PROCENT_DYSCYPLINY,
                    procent_subdyscypliny=PROCENT_SUBDYSCYPLINY,
                    wymiar_etatu=1,
                    rodzaj_autora=rodzaj_n,
                )
            )
    bulk_create_z_manifestem(
        ad_objs,
        model=Autor_Dyscyplina,
        label="bpp.Autor_Dyscyplina",
        desc="Dwudyscyplinowcy — dyscypliny",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )

    s = _load_slowniki()
    punktacja = punktacja_zrodel_mapping(zrodla_po_pk)
    prace: list[Wydawnictwo_Ciagle] = []
    przypisania: list[tuple[Autor, int]] = []
    for autor in autorzy:
        d1, d2 = pary[autor.pk]
        for k in range(prace_na_autora):
            rok = rng.choice(lata)
            dyscyplina = d2 if k % 2 == 0 else d1
            kandydaci = zrodla_wg_dyscypliny.get((rok, dyscyplina)) or list(
                zrodla_po_pk
            )
            praca = _build_praca(
                rng=rng,
                idx=idx_start + len(prace) + 1,
                rok=rok,
                zrodla=[zrodla_po_pk[rng.choice(kandydaci)]],
                s=s,
                theme=theme,
                punktacja=punktacja,
                marker=marker,
            )
            prace.append(praca)
            przypisania.append((autor, dyscyplina))
    bulk_create_z_manifestem(
        prace,
        model=Wydawnictwo_Ciagle,
        label="bpp.Wydawnictwo_Ciagle",
        desc="Dwudyscyplinowcy — artykuły",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )

    # Współautorzy: 0–2 autorów demo z dyscypliną za rok pracy.
    wspolautorzy = list(wspolautorzy)
    wsp_dyscypliny = autor_dyscyplina_mapping(wspolautorzy)
    wsp_jednostki = dict(
        Autor_Jednostka.objects.filter(
            autor_id__in=[a.pk for a in wspolautorzy]
        ).values_list("autor_id", "jednostka_id")
    )
    wspolautorzy = [a for a in wspolautorzy if a.pk in wsp_jednostki]
    jednostka_autora = {
        a.pk: j for a, (_i, _n, j, _p) in zip(autorzy, dane, strict=True)
    }

    powiazania = []
    for praca, (autor, dyscyplina) in zip(prace, przypisania, strict=True):
        powiazania.append(
            Wydawnictwo_Ciagle_Autor(
                rekord=praca,
                autor=autor,
                jednostka=jednostka_autora[autor.pk],
                typ_odpowiedzialnosci=s.aut_typ,
                kolejnosc=0,
                zapisany_jako=f"{autor.imiona} {autor.nazwisko}",
                afiliuje=True,
                dyscyplina_naukowa_id=dyscyplina,
                przypieta=True,
            )
        )
        ile = rng.randint(0, min(2, len(wspolautorzy)))
        for kolejnosc, wsp in enumerate(rng.sample(wspolautorzy, ile), start=1):
            powiazania.append(
                Wydawnictwo_Ciagle_Autor(
                    rekord=praca,
                    autor=wsp,
                    jednostka_id=wsp_jednostki[wsp.pk],
                    typ_odpowiedzialnosci=s.aut_typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{wsp.imiona} {wsp.nazwisko}",
                    afiliuje=True,
                    dyscyplina_naukowa_id=wsp_dyscypliny.get((wsp.pk, praca.rok)),
                    przypieta=True,
                )
            )
    bulk_create_z_manifestem(
        powiazania,
        model=Wydawnictwo_Ciagle_Autor,
        label="bpp.Wydawnictwo_Ciagle_Autor",
        desc="Dwudyscyplinowcy — autorzy prac",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    return autorzy, prace
