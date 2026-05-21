"""Generator Wydawnictwo_Zwarte + nadrzedne + powiazania."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from bpp.demo_data.generators._publikacje_common import (
    apply_denorm_pre_save_cache,
    autor_jednostka_mapping,
    make_doi,
    make_tytul,
)
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


@dataclass(frozen=True)
class _Slowniki:
    charaktery: list[Charakter_Formalny]
    typy_kbn: list[Typ_KBN]
    jezyki: list[Jezyk]
    statusy: list[Status_Korekty]
    aut_typ: Typ_Odpowiedzialnosci


def _load_slowniki() -> _Slowniki:
    """Wczytuje slowniki potrzebne do utworzenia Wydawnictwa_Zwarte.

    Charakter_Formalny i Typ_Odpowiedzialnosci sa wymagane (NOT NULL FK).
    Reszta — opcjonalna; w testach moga byc puste."""
    charaktery = list(Charakter_Formalny.objects.all())
    if not charaktery:
        raise ValueError("Brak Charakter_Formalny w bazie.")
    aut_typ = (
        Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first()
        or Typ_Odpowiedzialnosci.objects.first()
    )
    if aut_typ is None:
        raise ValueError("Brak Typ_Odpowiedzialnosci w bazie.")
    return _Slowniki(
        charaktery=charaktery,
        typy_kbn=list(Typ_KBN.objects.all()),
        jezyki=list(Jezyk.objects.all()),
        statusy=list(Status_Korekty.objects.all()),
        aut_typ=aut_typ,
    )


def _build_praca(
    *,
    rng: random.Random,
    idx: int,
    rok: int,
    wydawcy: list[Wydawca],
    s: _Slowniki,
    prefix: str = "",
) -> Wydawnictwo_Zwarte:
    tytul = make_tytul(rng, idx, prefix=prefix)
    praca = Wydawnictwo_Zwarte(
        tytul_oryginalny=tytul,
        rok=rok,
        charakter_formalny=rng.choice(s.charaktery),
        typ_kbn=rng.choice(s.typy_kbn) if s.typy_kbn else None,
        jezyk=rng.choice(s.jezyki) if s.jezyki else None,
        status_korekty=rng.choice(s.statusy) if s.statusy else None,
        wydawca=rng.choice(wydawcy),
        doi=make_doi(rng, rok, idx),
        punkty_kbn=rng.randint(5, 200),
    )
    apply_denorm_pre_save_cache(praca, tytul=tytul, kind="wz", idx=idx)
    return praca


def _bulk_create_with_manifest(
    *,
    objs: list[Wydawnictwo_Zwarte],
    desc: str,
    batch_size: int,
    manifest: Manifest,
    disable_progress: bool,
) -> list[Wydawnictwo_Zwarte]:
    """Bulk-create + manifest append w batch-ach, z paskiem postepu."""
    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc=desc,
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydawnictwo_Zwarte] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Wydawnictwo_Zwarte.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawnictwo_Zwarte", [p.pk for p in chunk])
        manifest.save()
    return created


def _build_powiazania(
    *,
    prace: list[Wydawnictwo_Zwarte],
    autorzy_z_jednostka: list[Autor],
    autor_to_jednostka: dict[int, int],
    aut_typ: Typ_Odpowiedzialnosci,
    rng: random.Random,
) -> list[Wydawnictwo_Zwarte_Autor]:
    """Buduje liste Wydawnictwo_Zwarte_Autor: 1–8 autorow per praca."""
    powiazania: list[Wydawnictwo_Zwarte_Autor] = []
    for praca in prace:
        liczba_autorow = rng.randint(1, min(8, len(autorzy_z_jednostka)))
        wybrani = rng.sample(autorzy_z_jednostka, liczba_autorow)
        for kolejnosc, autor in enumerate(wybrani):
            powiazania.append(
                Wydawnictwo_Zwarte_Autor(
                    rekord=praca,
                    autor=autor,
                    jednostka_id=autor_to_jednostka[autor.pk],
                    typ_odpowiedzialnosci=aut_typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{autor.imiona} {autor.nazwisko}",
                )
            )
    return powiazania


def create_wz(
    *,
    n: int,
    autorzy: Iterable[Autor],
    wydawcy: Iterable[Wydawca],
    lata: Iterable[int],
    manifest: Manifest,
    rng: random.Random,
    procent_rozdzialy: int = 20,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawnictwo_Zwarte]:
    """Tworzy n Wydawnictwo_Zwarte (zwykle + rozdzialy + nadrzedne).

    `procent_rozdzialy` (default 20%) sterujee podzialem: tyle % z n to
    rozdzialy z `wydawnictwo_nadrzedne` ustawionym na losowa ksiazke
    nadrzedna. Liczba ksiazek nadrzednych = 1 na ~5 rozdzialow (min. 1
    jesli sa rozdzialy). Nadrzedne sa stworzone jako PIERWSZE
    (zeby moc je przypisac do rozdzialow ktore powstaja po nich)."""
    autorzy = list(autorzy)
    wydawcy = list(wydawcy)
    lata = list(lata)

    if not autorzy:
        raise ValueError("Brak Autorow do podpiecia.")
    if not wydawcy:
        raise ValueError("Brak Wydawcow do podpiecia.")
    if not lata:
        raise ValueError("Brak lat — pusty zakres.")
    if not 0 <= procent_rozdzialy <= 100:
        raise ValueError(
            f"procent_rozdzialy musi byc w zakresie [0, 100], "
            f"dostal {procent_rozdzialy}"
        )

    s = _load_slowniki()
    autor_to_jednostka = autor_jednostka_mapping(autorzy)
    autorzy_z_jednostka = [a for a in autorzy if a.pk in autor_to_jednostka]
    if not autorzy_z_jednostka:
        raise ValueError(
            "Brak Autorow z przypisaniem do Jednostki — wymagane do "
            "utworzenia Wydawnictwo_Zwarte_Autor."
        )

    n_rozdzialow = (n * procent_rozdzialy) // 100
    n_zwyklych = n - n_rozdzialow
    # 1 ksiazka nadrzedna na ~5 rozdzialow; min. 1 gdy sa rozdzialy.
    n_nadrzednych = max(1, n_rozdzialow // 5) if n_rozdzialow else 0

    # 1. Najpierw nadrzedne ksiazki (zeby rozdzialy mogly je referencowac).
    nadrzedne_objs = [
        _build_praca(
            rng=rng,
            idx=i + 1,
            rok=rng.choice(lata),
            wydawcy=wydawcy,
            s=s,
            prefix=" Książka nadrzędna",
        )
        for i in range(n_nadrzednych)
    ]
    nadrzedne_created = _bulk_create_with_manifest(
        objs=nadrzedne_objs,
        desc="WZ nadrzędne",
        batch_size=batch_size,
        manifest=manifest,
        disable_progress=disable_progress,
    )

    # 2. Zwykle ksiazki + rozdzialy.
    pozostale_objs: list[Wydawnictwo_Zwarte] = []
    for i in range(n_zwyklych):
        pozostale_objs.append(
            _build_praca(
                rng=rng,
                idx=i + 1 + n_nadrzednych,
                rok=rng.choice(lata),
                wydawcy=wydawcy,
                s=s,
            )
        )
    for i in range(n_rozdzialow):
        praca = _build_praca(
            rng=rng,
            idx=i + 1 + n_nadrzednych + n_zwyklych,
            rok=rng.choice(lata),
            wydawcy=wydawcy,
            s=s,
            prefix=" Rozdział",
        )
        praca.wydawnictwo_nadrzedne = rng.choice(nadrzedne_created)
        pozostale_objs.append(praca)

    rng.shuffle(pozostale_objs)
    pozostale_created = _bulk_create_with_manifest(
        objs=pozostale_objs,
        desc="WZ zwykłe",
        batch_size=batch_size,
        manifest=manifest,
        disable_progress=disable_progress,
    )

    all_prace = nadrzedne_created + pozostale_created

    # 3. Powiazania autorow (1–8 per praca).
    powiazania = _build_powiazania(
        prace=all_prace,
        autorzy_z_jednostka=autorzy_z_jednostka,
        autor_to_jednostka=autor_to_jednostka,
        aut_typ=s.aut_typ,
        rng=rng,
    )

    pbar = make_progress(
        range(0, len(powiazania), batch_size),
        desc="WZ ↔ autorzy",
        total=(len(powiazania) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar:
        chunk = powiazania[start : start + batch_size]
        Wydawnictwo_Zwarte_Autor.objects.bulk_create(chunk)
        manifest.append("bpp.Wydawnictwo_Zwarte_Autor", [c.pk for c in chunk])
        manifest.save()

    return all_prace
