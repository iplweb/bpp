"""Generator Wydawnictwo_Zwarte + nadrzedne + powiazania."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from bpp import const
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
    poziomy_wydawcow_mapping,
    punkty_zwarte,
)
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
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
    charaktery_ksiazka: list[Charakter_Formalny]
    charaktery_rozdzial: list[Charakter_Formalny]
    typy_kbn: list[Typ_KBN]
    jezyki: list[Jezyk]
    statusy: list[Status_Korekty]
    aut_typ: Typ_Odpowiedzialnosci
    red_typ: Typ_Odpowiedzialnosci | None


def _load_slowniki() -> _Slowniki:
    """Wczytuje slowniki potrzebne do utworzenia Wydawnictwa_Zwarte.

    Charakter_Formalny i Typ_Odpowiedzialnosci sa wymagane (NOT NULL FK).
    Reszta — opcjonalna; w testach moga byc puste.

    Ksiazki dostaja charakter z `charakter_sloty` = ksiazka, rozdzialy —
    rozdzial (tak rozpoznaje je kalkulator slotow: `warunek_ksiazka` /
    `warunek_rozdzial`)."""
    charaktery = list(Charakter_Formalny.objects.all())
    if not charaktery:
        raise ValueError("Brak Charakter_Formalny w bazie.")
    aut_typ = (
        Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first()
        or Typ_Odpowiedzialnosci.objects.first()
    )
    if aut_typ is None:
        raise ValueError("Brak Typ_Odpowiedzialnosci w bazie.")
    red_typ = (
        Typ_Odpowiedzialnosci.objects.filter(skrot="red.").first()
        or Typ_Odpowiedzialnosci.objects.filter(typ_ogolny=const.TO_REDAKTOR).first()
    )
    return _Slowniki(
        charaktery_ksiazka=charaktery_wg(
            charaktery,
            charakter_ogolny=const.CHARAKTER_OGOLNY_KSIAZKA,
            charakter_sloty=const.CHARAKTER_SLOTY_KSIAZKA,
        ),
        charaktery_rozdzial=charaktery_wg(
            charaktery,
            charakter_ogolny=const.CHARAKTER_OGOLNY_ROZDZIAL,
            charakter_sloty=const.CHARAKTER_SLOTY_ROZDZIAL,
        ),
        typy_kbn=typy_kbn_liczone(list(Typ_KBN.objects.all())),
        jezyki=list(Jezyk.objects.all()),
        statusy=list(Status_Korekty.objects.all()),
        aut_typ=aut_typ,
        red_typ=red_typ,
    )


def _build_praca(
    *,
    rng: random.Random,
    idx: int,
    rok: int,
    wydawca: Wydawca,
    charaktery: list[Charakter_Formalny],
    s: _Slowniki,
    theme: Theme,
    marker: str = "",
    rola: str = "",
) -> Wydawnictwo_Zwarte:
    """Buduje (bez zapisu) Wydawnictwo_Zwarte. `punkty_kbn` ustawia pozniej
    `_ustaw_punkty` — zaleza od poziomu wydawcy i dyscyplin autorow."""
    tytul = make_tytul(theme, rng, idx, marker=marker, rola=rola)
    praca = Wydawnictwo_Zwarte(
        tytul_oryginalny=tytul,
        rok=rok,
        charakter_formalny=rng.choice(charaktery),
        typ_kbn=rng.choice(s.typy_kbn) if s.typy_kbn else None,
        jezyk=rng.choice(s.jezyki) if s.jezyki else None,
        status_korekty=rng.choice(s.statusy) if s.statusy else None,
        wydawca=wydawca,
        doi=make_doi(rng, rok, idx),
        punkty_kbn=0,
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
        bulk_create_retry(Wydawnictwo_Zwarte.objects, chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawnictwo_Zwarte", [p.pk for p in chunk])
        manifest.save()
    return created


def _build_powiazania(
    *,
    prace: list[Wydawnictwo_Zwarte],
    autorzy_z_jednostka: list[Autor],
    autor_to_jednostka: dict[int, int],
    autor_dyscyplina: dict[tuple[int, int], int],
    typ_dla_pracy: dict[int, Typ_Odpowiedzialnosci],
    rng: random.Random,
) -> list[Wydawnictwo_Zwarte_Autor]:
    """Buduje liste Wydawnictwo_Zwarte_Autor: 1–8 autorow per praca.

    `typ_dla_pracy` (id(praca) → typ odpowiedzialnosci) pozwala oznaczyc
    ksiazki nadrzedne jako redagowane. Autor z Autor_Dyscyplina za rok pracy
    dostaje te dyscypline (przypieta)."""
    powiazania: list[Wydawnictwo_Zwarte_Autor] = []
    for praca in prace:
        liczba_autorow = rng.randint(1, min(8, len(autorzy_z_jednostka)))
        wybrani = rng.sample(autorzy_z_jednostka, liczba_autorow)
        typ = typ_dla_pracy[id(praca)]
        for kolejnosc, autor in enumerate(wybrani):
            powiazania.append(
                Wydawnictwo_Zwarte_Autor(
                    rekord=praca,
                    autor=autor,
                    jednostka_id=autor_to_jednostka[autor.pk],
                    typ_odpowiedzialnosci=typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{autor.imiona} {autor.nazwisko}",
                    afiliuje=True,
                    dyscyplina_naukowa_id=autor_dyscyplina.get((autor.pk, praca.rok)),
                    przypieta=True,
                )
            )
    return powiazania


def _ustaw_punkty(
    *,
    prace: list[Wydawnictwo_Zwarte],
    powiazania: list[Wydawnictwo_Zwarte_Autor],
    rodzaj_dla_pracy: dict[int, str],
    poziomy: dict[tuple[int, int], int],
) -> None:
    """Ustawia punkty_kbn wg PROGI_ZWARTE (poziom wydawcy za rok pracy).

    Gdy WSZYSCY autorzy pracy z dyscyplina sa z dziedzin HST — wariant HST
    progow (tego oczekuje `_dopasuj_kalkulator`)."""
    hst = {d.pk: d.dyscyplina_hst for d in Dyscyplina_Naukowa.objects.all()}
    dyscypliny_pracy: dict[int, set[int]] = {}
    for p in powiazania:
        if p.dyscyplina_naukowa_id is not None:
            dyscypliny_pracy.setdefault(id(p.rekord), set()).add(
                p.dyscyplina_naukowa_id
            )
    for praca in prace:
        dyscypliny = dyscypliny_pracy.get(id(praca), set())
        tylko_hst = bool(dyscypliny) and all(hst.get(d) for d in dyscypliny)
        praca.punkty_kbn = punkty_zwarte(
            poziom=poziomy.get((praca.wydawca.pk, praca.rok)),
            rodzaj=rodzaj_dla_pracy[id(praca)],
            tylko_hst=tylko_hst,
        )


def create_wz(
    *,
    n: int,
    autorzy: Iterable[Autor],
    wydawcy: Iterable[Wydawca],
    lata: Iterable[int],
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    procent_rozdzialy: int = 20,
    prefix: str = "",
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawnictwo_Zwarte]:
    """Tworzy n Wydawnictwo_Zwarte (zwykle + rozdzialy + nadrzedne).

    Punkty wg `PROGI_ZWARTE` i poziomu wydawcy (Poziom_Wydawcy) za rok:
    zwykle ksiazki — monografia (autorstwo), nadrzedne — redakcja,
    rozdzialy — rozdzial (wydawca i rok jak w nadrzednej).

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

    # Rodzaj pracy (dla progow punktowych) i typ odpowiedzialnosci autorow,
    # kluczowane id(obiektu) — obiekty nie maja jeszcze PK.
    rodzaj_dla_pracy: dict[int, str] = {}
    typ_dla_pracy: dict[int, Typ_Odpowiedzialnosci] = {}

    # 1. Ksiazki nadrzedne (redagowane, jesli jest typ „red."; inaczej
    # autorskie).
    nadrzedne_objs: list[Wydawnictwo_Zwarte] = []
    for i in range(n_nadrzednych):
        praca = _build_praca(
            rng=rng,
            idx=i + 1,
            rok=rng.choice(lata),
            wydawca=rng.choice(wydawcy),
            charaktery=s.charaktery_ksiazka,
            s=s,
            theme=theme,
            marker=prefix,
            rola="Książka nadrzędna",
        )
        rodzaj_dla_pracy[id(praca)] = "RED" if s.red_typ else "KS"
        typ_dla_pracy[id(praca)] = s.red_typ or s.aut_typ
        nadrzedne_objs.append(praca)

    # 2. Zwykle ksiazki (autorskie) + rozdzialy (wydawca i rok z nadrzednej).
    pozostale_objs: list[Wydawnictwo_Zwarte] = []
    for i in range(n_zwyklych):
        praca = _build_praca(
            rng=rng,
            idx=i + 1 + n_nadrzednych,
            rok=rng.choice(lata),
            wydawca=rng.choice(wydawcy),
            charaktery=s.charaktery_ksiazka,
            s=s,
            theme=theme,
            marker=prefix,
        )
        rodzaj_dla_pracy[id(praca)] = "KS"
        typ_dla_pracy[id(praca)] = s.aut_typ
        pozostale_objs.append(praca)
    for i in range(n_rozdzialow):
        nadrzedna = rng.choice(nadrzedne_objs)
        praca = _build_praca(
            rng=rng,
            idx=i + 1 + n_nadrzednych + n_zwyklych,
            rok=nadrzedna.rok,
            wydawca=nadrzedna.wydawca,
            charaktery=s.charaktery_rozdzial,
            s=s,
            theme=theme,
            marker=prefix,
            rola="Rozdział",
        )
        praca.wydawnictwo_nadrzedne = nadrzedna
        rodzaj_dla_pracy[id(praca)] = "ROZ"
        typ_dla_pracy[id(praca)] = s.aut_typ
        pozostale_objs.append(praca)

    rng.shuffle(pozostale_objs)

    # 3. Powiazania autorow (1–8 per praca) — budowane PRZED zapisem prac,
    # bo punkty zaleza od dyscyplin autorow (wariant HST). Django przy
    # bulk_create powiazan bierze PK z zapisanych juz prac.
    powiazania = _build_powiazania(
        prace=nadrzedne_objs + pozostale_objs,
        autorzy_z_jednostka=autorzy_z_jednostka,
        autor_to_jednostka=autor_to_jednostka,
        autor_dyscyplina=autor_dyscyplina_mapping(autorzy_z_jednostka),
        typ_dla_pracy=typ_dla_pracy,
        rng=rng,
    )
    _ustaw_punkty(
        prace=nadrzedne_objs + pozostale_objs,
        powiazania=powiazania,
        rodzaj_dla_pracy=rodzaj_dla_pracy,
        poziomy=poziomy_wydawcow_mapping(w.pk for w in wydawcy),
    )

    nadrzedne_created = _bulk_create_with_manifest(
        objs=nadrzedne_objs,
        desc="WZ nadrzędne",
        batch_size=batch_size,
        manifest=manifest,
        disable_progress=disable_progress,
    )
    pozostale_created = _bulk_create_with_manifest(
        objs=pozostale_objs,
        desc="WZ zwykłe",
        batch_size=batch_size,
        manifest=manifest,
        disable_progress=disable_progress,
    )

    all_prace = nadrzedne_created + pozostale_created

    pbar = make_progress(
        range(0, len(powiazania), batch_size),
        desc="WZ ↔ autorzy",
        total=(len(powiazania) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar:
        chunk = powiazania[start : start + batch_size]
        bulk_create_retry(Wydawnictwo_Zwarte_Autor.objects, chunk)
        manifest.append("bpp.Wydawnictwo_Zwarte_Autor", [c.pk for c in chunk])
        manifest.save()

    return all_prace
