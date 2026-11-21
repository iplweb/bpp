"""Generator rzadziej używanych rodzajów rekordów i słowników.

Prace doktorskie i habilitacyjne, patenty (z autorami), konferencje
(podpięte do części prac ciągłych i zwartych), serie wydawnicze (części
książek), granty (``Grant_Rekordu`` przy części prac) i nagrody (przy
części książek). Wszystko w małej skali — chodzi o to, żeby filtry,
wyszukiwarka i raporty nie były puste.
"""

from __future__ import annotations

import datetime
import random
from collections.abc import Iterable
from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType

from bpp.demo_data.db import bulk_create_z_manifestem
from bpp.demo_data.generators._publikacje_common import (
    apply_denorm_pre_save_cache,
    make_tytul,
)
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix
from bpp.models import (
    Autor,
    Autor_Jednostka,
    Grant,
    Grant_Rekordu,
    Jezyk,
    Konferencja,
    Nagroda,
    Patent,
    Patent_Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Seria_Wydawnicza,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.nagroda import OrganPrzyznajacyNagrody

ZRODLA_FINANSOWANIA = (
    "Narodowe Centrum Nauki",
    "Narodowe Centrum Badań i Rozwoju",
    "Ministerstwo Nauki",
    "Program Horyzont Europa",
)


@dataclass
class RzadkieTypy:
    doktoraty: list = field(default_factory=list)
    habilitacje: list = field(default_factory=list)
    patenty: list = field(default_factory=list)
    konferencje: list = field(default_factory=list)
    serie: list = field(default_factory=list)
    granty: list = field(default_factory=list)
    nagrody: list = field(default_factory=list)

    def tekst(self) -> str:
        return (
            f"[OK] Rzadsze typy: {len(self.doktoraty)} doktoratów, "
            f"{len(self.habilitacje)} habilitacji, {len(self.patenty)} patentów, "
            f"{len(self.konferencje)} konferencji, {len(self.serie)} serii, "
            f"{len(self.granty)} grantów, {len(self.nagrody)} nagród.\n"
        )


@dataclass
class _Kontekst:
    autorzy: list
    jednostka_autora: dict
    lata: list
    theme: Theme
    rng: random.Random
    prefix: str
    bulk: dict
    tematy: list


def _prace_awansowe(k: _Kontekst, wynik: RzadkieTypy, ile_dr: int, ile_hab: int):
    """Prace doktorskie (z promotorem) i habilitacyjne (różni autorzy —
    ``Praca_Habilitacyjna.autor`` to OneToOne)."""
    status = Status_Korekty.objects.order_by("pk").first()
    typ_kbn = Typ_KBN.objects.order_by("pk").first()
    jezyk = (
        Jezyk.objects.filter(skrot__istartswith="pol").first()
        or Jezyk.objects.order_by("pk").first()
    )
    if not (status and typ_kbn and jezyk) or len(k.autorzy) < 2:
        return
    losowi = k.rng.sample(k.autorzy, min(len(k.autorzy), ile_dr + ile_hab))
    for i, autor in enumerate(losowi):
        habilitacja = i < ile_hab
        rola = "Rozprawa habilitacyjna:" if habilitacja else "Rozprawa doktorska:"
        tytul = make_tytul(k.theme, k.rng, i + 1, marker=k.prefix, rola=rola)
        praca = (Praca_Habilitacyjna if habilitacja else Praca_Doktorska)(
            tytul_oryginalny=tytul,
            rok=k.rng.choice(k.lata),
            status_korekty=status,
            typ_kbn=typ_kbn,
            jezyk=jezyk,
            autor=autor,
            jednostka_id=k.jednostka_autora[autor.pk],
        )
        if not habilitacja:
            praca.promotor = k.rng.choice([a for a in k.autorzy if a.pk != autor.pk])
        apply_denorm_pre_save_cache(
            praca, tytul=tytul, kind="hab" if habilitacja else "dr", idx=i + 1
        )
        (wynik.habilitacje if habilitacja else wynik.doktoraty).append(praca)
    bulk_create_z_manifestem(
        wynik.doktoraty,
        model=Praca_Doktorska,
        label="bpp.Praca_Doktorska",
        desc="Prace doktorskie",
        **k.bulk,
    )
    bulk_create_z_manifestem(
        wynik.habilitacje,
        model=Praca_Habilitacyjna,
        label="bpp.Praca_Habilitacyjna",
        desc="Prace habilitacyjne",
        **k.bulk,
    )


def _patent(k: _Kontekst, i: int, status, rodzaje_prawa) -> Patent:
    rok = k.rng.choice(k.lata)
    tytul = make_tytul(k.theme, k.rng, i + 1, marker=k.prefix, rola="Sposób:")
    zgloszenie = datetime.date(rok, k.rng.randint(1, 12), k.rng.randint(1, 28))
    patent = Patent(
        tytul_oryginalny=tytul,
        rok=rok,
        status_korekty=status,
        numer_zgloszenia=f"P.{rok}{k.rng.randint(10000, 99999)}",
        data_zgloszenia=zgloszenie,
        rodzaj_prawa=k.rng.choice(rodzaje_prawa) if rodzaje_prawa else None,
        wdrozenie=k.rng.random() < 0.3,
    )
    if k.rng.random() < 0.6:
        patent.data_decyzji = zgloszenie + datetime.timedelta(
            days=k.rng.randint(200, 700)
        )
        patent.numer_prawa_wylacznego = f"PL{k.rng.randint(200000, 249999)}"
    apply_denorm_pre_save_cache(patent, tytul=tytul, kind="pat", idx=i + 1)
    return patent


def _patenty(k: _Kontekst, wynik: RzadkieTypy, ile: int):
    from bpp.models import Rodzaj_Prawa_Patentowego

    status = Status_Korekty.objects.order_by("pk").first()
    aut_typ = (
        Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first()
        or Typ_Odpowiedzialnosci.objects.order_by("pk").first()
    )
    if not (status and aut_typ):
        return
    rodzaje_prawa = list(Rodzaj_Prawa_Patentowego.objects.order_by("pk"))
    wynik.patenty = [_patent(k, i, status, rodzaje_prawa) for i in range(ile)]
    bulk_create_z_manifestem(
        wynik.patenty, model=Patent, label="bpp.Patent", desc="Patenty", **k.bulk
    )
    patent_autorzy = []
    for patent in wynik.patenty:
        wybrani = k.rng.sample(k.autorzy, k.rng.randint(1, min(3, len(k.autorzy))))
        for kolejnosc, autor in enumerate(wybrani):
            patent_autorzy.append(
                Patent_Autor(
                    rekord=patent,
                    autor=autor,
                    jednostka_id=k.jednostka_autora[autor.pk],
                    typ_odpowiedzialnosci=aut_typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{autor.imiona} {autor.nazwisko}",
                    afiliuje=True,
                )
            )
    bulk_create_z_manifestem(
        patent_autorzy,
        model=Patent_Autor,
        label="bpp.Patent_Autor",
        desc="Patenty — autorzy",
        **k.bulk,
    )


def _konferencje(k: _Kontekst, wynik: RzadkieTypy, prace_wc, prace_wz):
    """6 konferencji podpiętych do ~5% prac ciągłych i zwartych."""
    for i, temat in enumerate(k.tematy[:6]):
        rok = k.rng.choice(k.lata)
        poczatek = datetime.date(rok, k.rng.randint(3, 11), k.rng.randint(1, 25))
        rodzaj = "Międzynarodowa" if i % 2 else "Krajowa"
        wynik.konferencje.append(
            Konferencja(
                nazwa=apply_prefix(f"{rodzaj} konferencja: {temat} {rok}", k.prefix),
                skrocona_nazwa=f"KONF-{rok}-{i + 1}",
                rozpoczecie=poczatek,
                zakonczenie=poczatek + datetime.timedelta(days=k.rng.randint(1, 3)),
                typ_konferencji=1 + i % 2,
            )
        )
    bulk_create_z_manifestem(
        wynik.konferencje,
        model=Konferencja,
        label="bpp.Konferencja",
        desc="Konferencje",
        **k.bulk,
    )
    if not wynik.konferencje:
        return
    for model, prace in (
        (Wydawnictwo_Ciagle, prace_wc),
        (Wydawnictwo_Zwarte, prace_wz),
    ):
        for praca in k.rng.sample(prace, len(prace) // 20):
            model.objects.filter(pk=praca.pk).update(
                konferencja=k.rng.choice(wynik.konferencje)
            )


def _serie(k: _Kontekst, wynik: RzadkieTypy, ksiazki):
    """3 serie wydawnicze; ~10% książek dostaje serię i numer w serii."""
    wynik.serie = [
        Seria_Wydawnicza(
            nazwa=apply_prefix(f"Biblioteka: {k.tematy[i % len(k.tematy)]}", k.prefix)
        )
        for i in range(3)
    ]
    bulk_create_z_manifestem(
        wynik.serie,
        model=Seria_Wydawnicza,
        label="bpp.Seria_Wydawnicza",
        desc="Serie wydawnicze",
        **k.bulk,
    )
    numery: dict[int, int] = {}
    for praca in k.rng.sample(ksiazki, len(ksiazki) // 10):
        seria = k.rng.choice(wynik.serie)
        numery[seria.pk] = numery.get(seria.pk, 0) + 1
        Wydawnictwo_Zwarte.objects.filter(pk=praca.pk).update(
            seria_wydawnicza=seria, numer_w_serii=str(numery[seria.pk])
        )


def _granty(k: _Kontekst, wynik: RzadkieTypy, prace_wc, prace_wz):
    """6 grantów przypiętych do ~3% prac."""
    for i in range(6):
        rok = k.rng.choice(k.lata)
        wynik.granty.append(
            Grant(
                numer_projektu=f"DEMO/{rok}/{i + 1:02d}",
                nazwa_projektu=apply_prefix(
                    f"Projekt: {k.tematy[i % len(k.tematy)]}", k.prefix
                ),
                zrodlo_finansowania=k.rng.choice(ZRODLA_FINANSOWANIA),
                rok=rok,
            )
        )
    bulk_create_z_manifestem(
        wynik.granty, model=Grant, label="bpp.Grant", desc="Granty", **k.bulk
    )
    granty_rekordow = []
    for model, prace in (
        (Wydawnictwo_Ciagle, prace_wc),
        (Wydawnictwo_Zwarte, prace_wz),
    ):
        ct = ContentType.objects.get_for_model(model)
        for praca in k.rng.sample(prace, len(prace) // 30):
            granty_rekordow.append(
                Grant_Rekordu(
                    content_type=ct,
                    object_id=praca.pk,
                    grant=k.rng.choice(wynik.granty),
                )
            )
    bulk_create_z_manifestem(
        granty_rekordow,
        model=Grant_Rekordu,
        label="bpp.Grant_Rekordu",
        desc="Granty — prace",
        **k.bulk,
    )


def _nagrody(k: _Kontekst, wynik: RzadkieTypy, ksiazki):
    """Dwa organy przyznające i nagrody dla kilku książek."""
    organy = [
        OrganPrzyznajacyNagrody(
            nazwa=apply_prefix("Minister Nauki", k.prefix), skrot="DEMO-MN"
        ),
        OrganPrzyznajacyNagrody(
            nazwa=apply_prefix("Polska Akademia Nauk", k.prefix), skrot="DEMO-PAN"
        ),
    ]
    bulk_create_z_manifestem(
        organy,
        model=OrganPrzyznajacyNagrody,
        label="bpp.OrganPrzyznajacyNagrody",
        desc="Organy przyznające nagrody",
        **k.bulk,
    )
    ct_wz = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)
    for praca in k.rng.sample(ksiazki, min(5, len(ksiazki))):
        wynik.nagrody.append(
            Nagroda(
                content_type=ct_wz,
                object_id=praca.pk,
                nazwa=k.rng.choice(("Nagroda za monografię", "Wyróżnienie")),
                organ_przyznajacy=k.rng.choice(organy),
                rok_przyznania=praca.rok + 1,
            )
        )
    bulk_create_z_manifestem(
        wynik.nagrody, model=Nagroda, label="bpp.Nagroda", desc="Nagrody", **k.bulk
    )


def create_rzadkie_typy(
    *,
    autorzy: Iterable[Autor],
    prace_wc: Iterable[Wydawnictwo_Ciagle],
    prace_wz: Iterable[Wydawnictwo_Zwarte],
    lata: Iterable[int],
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
    ile_doktoratow: int = 12,
    ile_habilitacji: int = 6,
    ile_patentow: int = 8,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> RzadkieTypy:
    autorzy = list(autorzy)
    prace_wc = list(prace_wc)
    prace_wz = list(prace_wz)
    lata = list(lata)
    wynik = RzadkieTypy()
    jednostka_autora = dict(
        Autor_Jednostka.objects.filter(
            autor_id__in=[a.pk for a in autorzy]
        ).values_list("autor_id", "jednostka_id")
    )
    autorzy = [a for a in autorzy if a.pk in jednostka_autora]
    if not autorzy or not lata:
        return wynik
    tematy = list(theme.tytul_topics)
    rng.shuffle(tematy)
    k = _Kontekst(
        autorzy=autorzy,
        jednostka_autora=jednostka_autora,
        lata=lata,
        theme=theme,
        rng=rng,
        prefix=prefix,
        bulk={
            "manifest": manifest,
            "batch_size": batch_size,
            "disable_progress": disable_progress,
        },
        tematy=tematy,
    )
    ksiazki = [p for p in prace_wz if p.wydawnictwo_nadrzedne_id is None]
    _prace_awansowe(k, wynik, ile_doktoratow, ile_habilitacji)
    _patenty(k, wynik, ile_patentow)
    _konferencje(k, wynik, prace_wc, prace_wz)
    _serie(k, wynik, ksiazki)
    _granty(k, wynik, prace_wc, prace_wz)
    _nagrody(k, wynik, ksiazki)
    return wynik
