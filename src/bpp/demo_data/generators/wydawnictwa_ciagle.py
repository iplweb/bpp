"""Generator Wydawnictwo_Ciagle + Wydawnictwo_Ciagle_Autor + DOI + OA."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from bpp.demo_data.db import bulk_create_retry
from bpp.demo_data.generators._publikacje_common import (
    apply_denorm_pre_save_cache,
    autor_dyscyplina_mapping,
    autor_jednostka_mapping,
    charaktery_wg,
    make_doi,
    make_tytul,
    typy_kbn_liczone,
)
from bpp.demo_data.generators.punktacja import (
    PUNKTY_SPOZA_WYKAZU,
    punktacja_zrodel_mapping,
)
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
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
        # Artykuly: charakter „art" — inaczej kalkulator slotow nie dopasuje.
        charaktery=charaktery_wg(charaktery, charakter_ogolny="art"),
        typy_kbn=typy_kbn_liczone(list(Typ_KBN.objects.all())),
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
    theme: Theme,
    punktacja: dict,
    marker: str = "",
) -> Wydawnictwo_Ciagle:
    tytul = make_tytul(theme, rng, idx, marker=marker)
    zrodlo = rng.choice(zrodla)
    praca = Wydawnictwo_Ciagle(
        tytul_oryginalny=tytul,
        rok=rok,
        charakter_formalny=rng.choice(s.charaktery),
        typ_kbn=rng.choice(s.typy_kbn) if s.typy_kbn else None,
        jezyk=rng.choice(s.jezyki) if s.jezyki else None,
        status_korekty=rng.choice(s.statusy) if s.statusy else None,
        zrodlo=zrodlo,
        doi=make_doi(rng, rok, idx),
        # Punkty = punktacja czasopisma za rok publikacji; spoza wykazu → 5.
        punkty_kbn=punktacja.get((zrodlo.pk, rok), PUNKTY_SPOZA_WYKAZU),
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
    autor_dyscyplina: dict[tuple[int, int], int] | None = None,
) -> list[Wydawnictwo_Ciagle_Autor]:
    """Buduje liste Wydawnictwo_Ciagle_Autor: 1–8 autorow per praca.

    Autor z Autor_Dyscyplina za rok pracy dostaje te dyscypline (przypieta)."""
    autor_dyscyplina = autor_dyscyplina or {}
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
                    afiliuje=True,
                    dyscyplina_naukowa_id=autor_dyscyplina.get((autor.pk, praca.rok)),
                    przypieta=True,
                )
            )
    return powiazania


def create_wc(
    *,
    n: int,
    autorzy: Iterable[Autor],
    zrodla: Iterable[Zrodlo],
    lata: Iterable[int],
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
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
    punktacja = punktacja_zrodel_mapping(z.pk for z in zrodla)
    autor_to_jednostka = autor_jednostka_mapping(autorzy)
    autorzy_z_jednostka = [a for a in autorzy if a.pk in autor_to_jednostka]
    if not autorzy_z_jednostka:
        raise ValueError(
            "Brak Autorow z przypisaniem do Jednostki — wymagane do "
            "utworzenia Wydawnictwo_Ciagle_Autor."
        )

    prace = [
        _build_praca(
            rng=rng,
            idx=i + 1,
            rok=rng.choice(lata),
            zrodla=zrodla,
            s=s,
            theme=theme,
            punktacja=punktacja,
            marker=prefix,
        )
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
        bulk_create_retry(Wydawnictwo_Ciagle.objects, chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawnictwo_Ciagle", [p.pk for p in chunk])
        manifest.save()

    powiazania = _build_powiazania(
        created=created,
        autorzy_z_jednostka=autorzy_z_jednostka,
        autor_to_jednostka=autor_to_jednostka,
        aut_typ=s.aut_typ,
        rng=rng,
        autor_dyscyplina=autor_dyscyplina_mapping(autorzy_z_jednostka),
    )

    pbar2 = make_progress(
        range(0, len(powiazania), batch_size),
        desc="WC ↔ autorzy",
        total=(len(powiazania) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar2:
        chunk = powiazania[start : start + batch_size]
        bulk_create_retry(Wydawnictwo_Ciagle_Autor.objects, chunk)
        manifest.append("bpp.Wydawnictwo_Ciagle_Autor", [c.pk for c in chunk])
        manifest.save()

    return created
