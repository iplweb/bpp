"""Celowe „brudy" w danych demo — żeby narzędzia porządkowe miały co pokazać.

- Zdublowani autorzy (to samo imię i nazwisko, inicjał zamiast imienia,
  nazwisko dwuczłonowe) z jedną pracą „przeniesioną" od oryginału —
  ``deduplikator_autorow``. Duplikat nie ma dyscypliny, więc jego praca
  z dyscypliną trafia też do rozbieżności dyscyplin („brak przypisania").
- Zdublowane czasopisma (ten sam ISSN, inna nazwa, bez odpowiednika w PBN)
  z jedną pracą — ``deduplikator_zrodel`` (oryginał musi mieć odpowiednik
  w PBN z numerem MNiSW — robi to generator PBN).
- Zdublowane prace ciągłe (ten sam tytuł, rok i czasopismo; część także
  z tym samym DOI) — ``deduplikator_publikacji``.
- Rozbieżne dyscypliny autorów prac (dyscyplina spoza przypisań autora za
  dany rok albo jej brak) — ``rozbieznosci_dyscyplin``.
- Punkty pracy inne niż punktacja czasopisma za rok — ``rozbieznosci``.

Uruchamiane PRZED przeliczeniem ewaluacji, więc cache slotów i liczba N
uwzględniają te zmiany.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from bpp.demo_data.db import bulk_create_z_manifestem
from bpp.demo_data.generators._publikacje_common import apply_denorm_pre_save_cache
from bpp.demo_data.generators.autorzy import utworz_autorow
from bpp.demo_data.manifest import Manifest
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Autor_Jednostka,
    Dyscyplina_Naukowa,
    Punktacja_Zrodla,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)


@dataclass
class Brudy:
    autorzy: list = field(default_factory=list)
    zrodla: list = field(default_factory=list)
    prace: list = field(default_factory=list)
    rozbiezne_dyscypliny: int = 0
    rozbiezne_punkty: int = 0

    def tekst(self) -> str:
        return (
            f"[OK] Celowe brudy: {len(self.autorzy)} zdublowanych autorów, "
            f"{len(self.zrodla)} czasopism, {len(self.prace)} prac; "
            f"{self.rozbiezne_dyscypliny} rozbieżnych dyscyplin, "
            f"{self.rozbiezne_punkty} rozbieżnych punktacji.\n"
        )


def _wariant_imienia(imiona: str, nr: int, inne_nazwiska: list[str], nazwisko: str):
    """(imiona, nazwisko) duplikatu: kopia, inicjał albo nazwisko dwuczłonowe."""
    if nr % 3 == 0:
        return imiona, nazwisko
    if nr % 3 == 1:
        return f"{imiona[0]}.", nazwisko
    drugie = next((n for n in inne_nazwiska if n != nazwisko), "Nowak")
    return imiona, f"{nazwisko}-{drugie}"


def _zdubluj_autorow(*, autorzy, ile, manifest, rng, batch_size, disable_progress):
    """Duplikaty autorów, którzy mają co najmniej 2 prace ciągłe."""
    wca_autora = defaultdict(list)
    for wca_id, autor_id in (
        Wydawnictwo_Ciagle_Autor.objects.filter(autor__in=autorzy)
        .order_by("pk")
        .values_list("pk", "autor_id")
    ):
        wca_autora[autor_id].append(wca_id)
    kandydaci = [a for a in autorzy if len(wca_autora[a.pk]) >= 2]
    if not kandydaci:
        return []
    oryginaly = rng.sample(kandydaci, min(ile, len(kandydaci)))
    jednostka = dict(
        Autor_Jednostka.objects.filter(autor__in=oryginaly).values_list(
            "autor_id", "jednostka_id"
        )
    )
    nazwiska = sorted({a.nazwisko for a in autorzy})
    dane = []
    for nr, oryginal in enumerate(oryginaly):
        imiona, nazwisko = _wariant_imienia(
            oryginal.imiona,
            nr,
            rng.sample(nazwiska, min(3, len(nazwiska))),
            oryginal.nazwisko,
        )
        dane.append((imiona, nazwisko, jednostka[oryginal.pk], {}))
    duplikaty = utworz_autorow(
        dane,
        slug_tag="duplikat",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
        desc="Brudy — zdublowani autorzy",
    )
    for oryginal, duplikat in zip(oryginaly, duplikaty, strict=True):
        wca_id = rng.choice(wca_autora[oryginal.pk])
        Wydawnictwo_Ciagle_Autor.objects.filter(pk=wca_id).update(
            autor=duplikat,
            zapisany_jako=f"{duplikat.imiona} {duplikat.nazwisko}",
        )
    return duplikaty


def _zdubluj_zrodla(*, zrodla, ile, manifest, rng, batch_size, disable_progress):
    """Czasopisma z tym samym ISSN co oryginał; jedna praca przeniesiona."""
    prace_zrodla = defaultdict(list)
    for wc_id, zrodlo_id in (
        Wydawnictwo_Ciagle.objects.filter(zrodlo__in=zrodla)
        .order_by("pk")
        .values_list("pk", "zrodlo_id")
    ):
        prace_zrodla[zrodlo_id].append(wc_id)
    kandydaci = [z for z in zrodla if z.issn and len(prace_zrodla[z.pk]) >= 2]
    oryginaly = rng.sample(kandydaci, min(ile, len(kandydaci)))
    duplikaty = []
    for i, z in enumerate(oryginaly):
        nazwa = f"{z.nazwa} (wydanie elektroniczne)" if i % 2 else z.nazwa.upper()
        duplikaty.append(
            Zrodlo(
                nazwa=nazwa,
                skrot=f"{z.skrot}-DUP",
                rodzaj_id=z.rodzaj_id,
                zasieg_id=z.zasieg_id,
                issn=z.issn,
                slug=f"{z.slug}-duplikat",
            )
        )
    bulk_create_z_manifestem(
        duplikaty,
        model=Zrodlo,
        label="bpp.Zrodlo",
        desc="Brudy — zdublowane czasopisma",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    for oryginal, duplikat in zip(oryginaly, duplikaty, strict=True):
        wc_id = rng.choice(prace_zrodla[oryginal.pk])
        Wydawnictwo_Ciagle.objects.filter(pk=wc_id).update(zrodlo=duplikat)
    return duplikaty


def _zdubluj_prace(
    *, prace, ile, idx_start, manifest, rng, batch_size, disable_progress
):
    """Kopie prac ciągłych: ten sam tytuł, rok, czasopismo i autorzy;
    co druga także z tym samym DOI."""
    oryginaly = rng.sample(prace, min(ile, len(prace)))
    kopie = []
    for i, oryginal in enumerate(oryginaly):
        kopia = Wydawnictwo_Ciagle.objects.get(pk=oryginal.pk)
        kopia.pk = None
        kopia.id = None
        kopia._state.adding = True
        kopia.pbn_uid = None
        if i % 2:
            kopia.doi = None
        apply_denorm_pre_save_cache(
            kopia, tytul=kopia.tytul_oryginalny, kind="wc", idx=idx_start + i + 1
        )
        kopie.append(kopia)
    bulk_create_z_manifestem(
        kopie,
        model=Wydawnictwo_Ciagle,
        label="bpp.Wydawnictwo_Ciagle",
        desc="Brudy — zdublowane prace",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    autorzy_kopii = []
    for oryginal, kopia in zip(oryginaly, kopie, strict=True):
        for wca in Wydawnictwo_Ciagle_Autor.objects.filter(rekord=oryginal).order_by(
            "kolejnosc"
        ):
            wca.pk = None
            wca.id = None
            wca._state.adding = True
            wca.rekord = kopia
            autorzy_kopii.append(wca)
    bulk_create_z_manifestem(
        autorzy_kopii,
        model=Wydawnictwo_Ciagle_Autor,
        label="bpp.Wydawnictwo_Ciagle_Autor",
        desc="Brudy — autorzy zdublowanych prac",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    return kopie


def _rozbiezne_dyscypliny(*, prace, ile, rng) -> int:
    """Część przypisań autor–praca: dyscyplina spoza przypisań autora za rok
    (co trzecie: brak dyscypliny, choć autor ją ma)."""
    wca = list(
        Wydawnictwo_Ciagle_Autor.objects.filter(
            rekord__in=prace, dyscyplina_naukowa__isnull=False
        )
        .order_by("pk")
        .values_list("pk", "autor_id", "rekord__rok")
    )
    dyscypliny = list(
        Dyscyplina_Naukowa.objects.order_by("pk").values_list("pk", flat=True)
    )
    if not wca or len(dyscypliny) < 3:
        return 0
    zmienione = 0
    for nr, (wca_id, autor_id, rok) in enumerate(rng.sample(wca, min(ile, len(wca)))):
        ad = Autor_Dyscyplina.objects.filter(autor_id=autor_id, rok=rok).first()
        if ad is None:
            continue
        if nr % 3 == 2:
            nowa = None
        else:
            wlasne = {ad.dyscyplina_naukowa_id, ad.subdyscyplina_naukowa_id}
            nowa = rng.choice([d for d in dyscypliny if d not in wlasne])
        Wydawnictwo_Ciagle_Autor.objects.filter(pk=wca_id).update(
            dyscyplina_naukowa_id=nowa
        )
        zmienione += 1
    return zmienione


def _rozbiezne_punkty(*, prace, ile, rng) -> int:
    """Część prac dostaje punkty inne niż punktacja czasopisma za rok."""
    punktacja = {
        (zrodlo_id, rok): punkty
        for zrodlo_id, rok, punkty in Punktacja_Zrodla.objects.filter(
            zrodlo_id__in={p.zrodlo_id for p in prace}
        ).values_list("zrodlo_id", "rok", "punkty_kbn")
    }
    kandydaci = [p for p in prace if punktacja.get((p.zrodlo_id, p.rok))]
    zmienione = 0
    for praca in rng.sample(kandydaci, min(ile, len(kandydaci))):
        stare = punktacja[(praca.zrodlo_id, praca.rok)]
        nowe = stare + Decimal(rng.choice((-20, -10, 10, 20)))
        Wydawnictwo_Ciagle.objects.filter(pk=praca.pk).update(
            punkty_kbn=max(nowe, Decimal(5))
        )
        zmienione += 1
    return zmienione


def create_brudy(
    *,
    autorzy: Iterable[Autor],
    zrodla: Iterable[Zrodlo],
    prace_wc: Iterable[Wydawnictwo_Ciagle],
    idx_start: int,
    manifest: Manifest,
    rng: random.Random,
    ile_autorow: int = 6,
    ile_zrodel: int = 3,
    ile_prac: int = 6,
    ile_dyscyplin: int = 12,
    ile_punktow: int = 8,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> Brudy:
    """``idx_start`` — numer ostatniej pracy ciągłej demo (unikalny slug)."""
    autorzy = list(autorzy)
    zrodla = list(zrodla)
    prace_wc = list(prace_wc)
    bulk = {
        "manifest": manifest,
        "rng": rng,
        "batch_size": batch_size,
        "disable_progress": disable_progress,
    }
    wynik = Brudy()
    # Kolejność: najpierw rozbieżności na oryginałach, potem duplikaty
    # (kopie prac dziedziczą wtedy już „zabrudzone" przypisania tylko
    # przypadkiem — nie szkodzi).
    wynik.rozbiezne_dyscypliny = _rozbiezne_dyscypliny(
        prace=prace_wc, ile=ile_dyscyplin, rng=rng
    )
    wynik.rozbiezne_punkty = _rozbiezne_punkty(prace=prace_wc, ile=ile_punktow, rng=rng)
    wynik.autorzy = _zdubluj_autorow(autorzy=autorzy, ile=ile_autorow, **bulk)
    wynik.zrodla = _zdubluj_zrodla(zrodla=zrodla, ile=ile_zrodel, **bulk)
    wynik.prace = _zdubluj_prace(
        prace=prace_wc, ile=ile_prac, idx_start=idx_start, **bulk
    )
    return wynik
