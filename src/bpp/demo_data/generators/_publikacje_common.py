"""Wspolne helpery dla generatorow publikacji (WC, WZ).

Wyodrebnione przed implementacja generatora Wydawnictwo_Zwarte zeby uniknac
copy-paste drift miedzy generatorami. Pola DOI, tytulow i mapping
autor->jednostka sa wspolne; OA modele rozne (osobne tabele dla WC i WZ),
wiec OA pozostaje per-generator."""

from __future__ import annotations

import random

from django.utils.text import slugify

from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import compose_tytul
from bpp.models import Autor, Autor_Jednostka

DENORM_CACHE_FIELDS: tuple[str, ...] = (
    "cached_punkty_dyscyplin",
    "opis_bibliograficzny_cache",
    "opis_bibliograficzny_autorzy_cache",
    "opis_bibliograficzny_zapisani_autorzy_cache",
    "slug",
)


def make_tytul(
    theme: Theme,
    rng: random.Random,
    idx: int,
    *,
    marker: str = "",
    rola: str = "",
) -> str:
    """Tytuł: '<marker><rola> <treść> (nr idx)'.

    `marker` — wizualny prefiks demo ('Demo — ' lub '').
    `rola` — etykieta roli publikacji ('Rozdział' / 'Książka nadrzędna' / '').
    """
    body = compose_tytul(theme, rng)
    rola_part = f"{rola} " if rola else ""
    return f"{marker}{rola_part}{body} (nr {idx})"


def make_doi(rng: random.Random, rok: int, idx: int) -> str:
    """Generuje syntetyczny DOI w formacie `10.NNNN/demo.YYYY.IDX`."""
    prefix4 = rng.randint(1000, 9999)
    return f"10.{prefix4}/demo.{rok}.{idx}"


def apply_denorm_pre_save_cache(obj, *, tytul: str, kind: str, idx: int) -> None:
    """Pre-set `@denormalized` pola na obj + ich `_denorm_pre_save_<attname>`
    cache, zeby `denorm.fields.pre_save` zwracal cache i NIE wywolal
    callback funkcji.

    Po co: w trakcie `bulk_create` Django wola `Field.pre_save(obj, add=True)`
    dla kazdego pola PRZED INSERT-em. `denorm` registers `pre_save` jako
    field-level (nie sygnal), wiec bulk_create JE odpala. Callbacki typu
    `cached_punkty_dyscyplin` -> `przelicz_punkty_dyscyplin()` -> ISlot ->
    `original.zewnetrzna_baza_danych.filter(...)` wymagaja PK i wywalaja
    sie ValueError-em. `denorm/fields.py:pre_save` ma cache short-circuit
    (`if cached is not None: return cached`), wiec pre-set non-None cache
    omija callbacka.

    Wartosci to placeholdery (puste tekst/listy, slug z disambiguatorem
    `kind-idx`). Po `create_demo_data` user powinien uruchomic
    `manage.py denorm_flush` zeby wypelnic cache prawdziwymi wartosciami
    (juz sugerowane w stdout banner).

    `kind` ('wc'/'wz') + `idx` (unique w obrebie generation run) gwarantuja
    unique slug (SlugField ma unique=True). Cross-run uniqueness zalezy
    od czystej bazy lub uprzedniego cleanup_demo_data.
    """
    safe_tytul = (tytul or "")[:60]
    slug_value = slugify(f"{safe_tytul}-{kind}-{idx}")[:400]
    if not slug_value:
        slug_value = f"demo-{kind}-{idx}"

    defaults: dict[str, object] = {
        "cached_punkty_dyscyplin": [],
        "opis_bibliograficzny_cache": tytul,
        "opis_bibliograficzny_autorzy_cache": [],
        "opis_bibliograficzny_zapisani_autorzy_cache": "",
        "slug": slug_value,
    }
    for attname, value in defaults.items():
        setattr(obj, attname, value)
        setattr(obj, f"_denorm_pre_save_{attname}", value)


def autor_jednostka_mapping(autorzy: list[Autor]) -> dict[int, int]:
    """Mapping autor_id -> jednostka_id z Autor_Jednostka.

    `BazaModeluOdpowiedzialnosciAutorow.jednostka` jest NOT NULL FK
    (CASCADE, bez `null=True`) — dotyczy zarowno
    `Wydawnictwo_Ciagle_Autor` jak i `Wydawnictwo_Zwarte_Autor`.
    Pre-fetchujemy mapping dla wszystkich autorow zeby unikac N+1."""
    return dict(
        Autor_Jednostka.objects.filter(
            autor_id__in=[a.pk for a in autorzy]
        ).values_list("autor_id", "jednostka_id")
    )
