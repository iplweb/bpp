"""Generator Wydawnictwo_Ciagle + Wydawnictwo_Ciagle_Autor + DOI + OA."""

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
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)


def _maybe_openaccess(rng: random.Random) -> dict:
    """Zwraca dict do **kwargs Wydawnictwo_Ciagle — z prawd. 50% wypelnia
    pola Open Access. Modele OA sa opcjonalne; jesli pusto, zwraca {}."""
    from bpp.models.openaccess import (
        Licencja_OpenAccess,
        Tryb_OpenAccess_Wydawnictwo_Ciagle,
        Wersja_Tekstu_OpenAccess,
    )

    if rng.randint(0, 1) == 0:
        return {}

    out: dict = {}
    tryb = Tryb_OpenAccess_Wydawnictwo_Ciagle.objects.order_by("?").first()
    if tryb:
        out["openaccess_tryb_dostepu"] = tryb
    wersja = Wersja_Tekstu_OpenAccess.objects.order_by("?").first()
    if wersja:
        out["openaccess_wersja_tekstu"] = wersja
    licencja = Licencja_OpenAccess.objects.order_by("?").first()
    if licencja:
        out["openaccess_licencja"] = licencja
    return out


@dataclass(frozen=True)
class _Slowniki:
    charaktery: list[Charakter_Formalny]
    typy_kbn: list[Typ_KBN]
    jezyki: list[Jezyk]
    statusy: list[Status_Korekty]
    aut_typ: Typ_Odpowiedzialnosci


def _load_slowniki() -> _Slowniki:
    """Wczytuje slowniki potrzebne do utworzenia Wydawnictwa_Ciagle.

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
    zrodla: list[Zrodlo],
    s: _Slowniki,
) -> Wydawnictwo_Ciagle:
    tytul = make_tytul(rng, idx)
    praca = Wydawnictwo_Ciagle(
        tytul_oryginalny=tytul,
        rok=rok,
        charakter_formalny=rng.choice(s.charaktery),
        typ_kbn=rng.choice(s.typy_kbn) if s.typy_kbn else None,
        jezyk=rng.choice(s.jezyki) if s.jezyki else None,
        status_korekty=rng.choice(s.statusy) if s.statusy else None,
        zrodlo=rng.choice(zrodla),
        doi=make_doi(rng, rok, idx),
        punkty_kbn=rng.randint(5, 200),
        **_maybe_openaccess(rng),
    )
    apply_denorm_pre_save_cache(praca, tytul=tytul, kind="wc", idx=idx)
    return praca


def _build_powiazania(
    *,
    created: list[Wydawnictwo_Ciagle],
    autorzy_z_jednostka: list[Autor],
    autor_to_jednostka: dict[int, int],
    aut_typ: Typ_Odpowiedzialnosci,
    rng: random.Random,
) -> list[Wydawnictwo_Ciagle_Autor]:
    """Buduje liste Wydawnictwo_Ciagle_Autor: 1–8 autorow per praca."""
    powiazania: list[Wydawnictwo_Ciagle_Autor] = []
    for praca in created:
        liczba_autorow = rng.randint(1, min(8, len(autorzy_z_jednostka)))
        wybrani = rng.sample(autorzy_z_jednostka, liczba_autorow)
        for kolejnosc, autor in enumerate(wybrani):
            powiazania.append(
                Wydawnictwo_Ciagle_Autor(
                    rekord=praca,
                    autor=autor,
                    jednostka_id=autor_to_jednostka[autor.pk],
                    typ_odpowiedzialnosci=aut_typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{autor.imiona} {autor.nazwisko}",
                )
            )
    return powiazania


def create_wc(
    *,
    n: int,
    autorzy: Iterable[Autor],
    zrodla: Iterable[Zrodlo],
    lata: Iterable[int],
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawnictwo_Ciagle]:
    """Tworzy n Wydawnictwo_Ciagle + powiazania autorow (1–8 na prace)."""
    autorzy = list(autorzy)
    zrodla = list(zrodla)
    lata = list(lata)

    if not autorzy:
        raise ValueError("Brak Autorow do podpiecia.")
    if not zrodla:
        raise ValueError("Brak Zrodel do podpiecia.")
    if not lata:
        raise ValueError("Brak lat — pusty zakres.")

    s = _load_slowniki()
    autor_to_jednostka = autor_jednostka_mapping(autorzy)
    autorzy_z_jednostka = [a for a in autorzy if a.pk in autor_to_jednostka]
    if not autorzy_z_jednostka:
        raise ValueError(
            "Brak Autorow z przypisaniem do Jednostki — wymagane do "
            "utworzenia Wydawnictwo_Ciagle_Autor."
        )

    prace = [
        _build_praca(rng=rng, idx=i + 1, rok=rng.choice(lata), zrodla=zrodla, s=s)
        for i in range(n)
    ]

    pbar = make_progress(
        range(0, n, batch_size),
        desc="Wydawnictwa ciągłe",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydawnictwo_Ciagle] = []
    for start in pbar:
        chunk = prace[start : start + batch_size]
        Wydawnictwo_Ciagle.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawnictwo_Ciagle", [p.pk for p in chunk])
        manifest.save()

    powiazania = _build_powiazania(
        created=created,
        autorzy_z_jednostka=autorzy_z_jednostka,
        autor_to_jednostka=autor_to_jednostka,
        aut_typ=s.aut_typ,
        rng=rng,
    )

    pbar2 = make_progress(
        range(0, len(powiazania), batch_size),
        desc="WC ↔ autorzy",
        total=(len(powiazania) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar2:
        chunk = powiazania[start : start + batch_size]
        Wydawnictwo_Ciagle_Autor.objects.bulk_create(chunk)
        manifest.append("bpp.Wydawnictwo_Ciagle_Autor", [c.pk for c in chunk])
        manifest.save()

    return created
