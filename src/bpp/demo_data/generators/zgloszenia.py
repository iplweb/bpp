"""Generator zgłoszeń publikacji (``zglos_publikacje``) w różnych stanach."""

from __future__ import annotations

import random
import uuid
from collections.abc import Iterable

from django.utils.text import slugify

from bpp.demo_data.db import bulk_create_z_manifestem
from bpp.demo_data.generators._publikacje_common import (
    autor_dyscyplina_mapping,
    make_tytul,
)
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.base import Theme
from bpp.models import Autor, Autor_Jednostka, Typ_Odpowiedzialnosci


def create_zgloszenia(
    *,
    autorzy: Iterable[Autor],
    lata: Iterable[int],
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
    ile: int = 10,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list:
    from zglos_publikacje.models import (
        Zgloszenie_Publikacji,
        Zgloszenie_Publikacji_Autor,
    )

    S = Zgloszenie_Publikacji.Statusy
    R = Zgloszenie_Publikacji.Rodzaje
    # Najwięcej nowych — to one czekają na redaktora:
    statusy = [S.NOWY] * 4 + [S.WYMAGA_ZMIAN, S.PO_ZMIANACH, S.ODRZUCONO, S.SPAM]
    rodzaje = [R.ARTYKUL, R.ROZDZIAL_W_MONOGRAFII, R.MONOGRAFIA, R.INNE]

    autorzy = list(autorzy)
    lata = list(lata)
    jednostka = dict(
        Autor_Jednostka.objects.filter(
            autor_id__in=[a.pk for a in autorzy]
        ).values_list("autor_id", "jednostka_id")
    )
    autorzy = [a for a in autorzy if a.pk in jednostka]
    aut_typ = (
        Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first()
        or Typ_Odpowiedzialnosci.objects.order_by("pk").first()
    )
    if not autorzy or not lata or aut_typ is None:
        return []

    zgloszenia, zglaszajacy = [], []
    for i in range(ile):
        autor = rng.choice(autorzy)
        status = statusy[i % len(statusy)]
        zgl = Zgloszenie_Publikacji(
            tytul_oryginalny=make_tytul(theme, rng, i + 1, marker=prefix),
            rok=rng.choice(lata[-3:]),
            email=f"{slugify(autor.imiona)}.{slugify(autor.nazwisko)}@example.org",
            rodzaj_zglaszanej_publikacji=rodzaje[i % len(rodzaje)],
            status=status,
            strona_www=f"https://example.org/publikacja/{i + 1}",
        )
        if status == S.WYMAGA_ZMIAN:
            zgl.kod_do_edycji = uuid.uuid4()
            zgl.przyczyna_zwrotu = "Proszę uzupełnić DOI i numer strony."
        zgloszenia.append(zgl)
        zglaszajacy.append(autor)
    bulk_create_z_manifestem(
        zgloszenia,
        model=Zgloszenie_Publikacji,
        label="zglos_publikacje.Zgloszenie_Publikacji",
        desc="Zgłoszenia publikacji",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )

    dyscypliny = autor_dyscyplina_mapping(autorzy)
    powiazania = []
    for zgl, autor in zip(zgloszenia, zglaszajacy, strict=True):
        wspolautorzy = [a for a in autorzy if a.pk != autor.pk]
        dodatkowi = rng.sample(wspolautorzy, min(len(wspolautorzy), rng.randint(0, 2)))
        for kolejnosc, a in enumerate([autor, *dodatkowi]):
            powiazania.append(
                Zgloszenie_Publikacji_Autor(
                    rekord=zgl,
                    rok=zgl.rok,
                    autor=a,
                    jednostka_id=jednostka[a.pk],
                    typ_odpowiedzialnosci=aut_typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{a.imiona} {a.nazwisko}",
                    dyscyplina_naukowa_id=dyscypliny.get((a.pk, zgl.rok)),
                )
            )
    bulk_create_z_manifestem(
        powiazania,
        model=Zgloszenie_Publikacji_Autor,
        label="zglos_publikacje.Zgloszenie_Publikacji_Autor",
        desc="Zgłoszenia — autorzy",
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )
    return zgloszenia
