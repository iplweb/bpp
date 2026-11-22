"""Motyw 'miks' — wszystkie motywy fabularne naraz (największa różnorodność).

Pule imion, nazwisk, tytułów, czasopism, wydawców i jednostek to suma pul
motywów Lem, Wiedźmin, Harry Potter, Disney, Mitologia i Trylogia (bez
powtórek, w kolejności motywów). Motyw „realistyczny” celowo pominięty —
prawdziwe nazwiska obok fikcyjnych wyglądałyby dziwnie.
"""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.disney import DISNEY
from bpp.demo_data.themes.harry_potter import HARRY_POTTER
from bpp.demo_data.themes.lem import LEM
from bpp.demo_data.themes.mitologia import MITOLOGIA
from bpp.demo_data.themes.trylogia import TRYLOGIA
from bpp.demo_data.themes.wiedzmin import WIEDZMIN

SKLADNIKI: tuple[Theme, ...] = (
    LEM,
    WIEDZMIN,
    HARRY_POTTER,
    DISNEY,
    MITOLOGIA,
    TRYLOGIA,
)


def _suma(pole: str) -> tuple:
    """Pula ``pole`` ze wszystkich składników, bez powtórek, z zachowaniem
    kolejności."""
    return tuple(dict.fromkeys(x for t in SKLADNIKI for x in getattr(t, pole)))


MIKS = Theme(
    key="miks",
    label="Miks wszystkich motywów",
    uczelnia_nazwy=(
        "Uniwersytet Wszystkich Światów",
        "Międzyświatowa Akademia Nauk Stosowanych",
    ),
    uczelnia_skrot="UWŚ",
    wydzial_dziedziny=_suma("wydzial_dziedziny"),
    jednostka_dziedziny=_suma("jednostka_dziedziny"),
    autor_imiona=_suma("autor_imiona"),
    autor_nazwiska=_suma("autor_nazwiska"),
    zrodlo_human=_suma("zrodlo_human"),
    wydawcy=_suma("wydawcy"),
    tytul_topics=_suma("tytul_topics"),
    tytul_subjects=_suma("tytul_subjects"),
    tytul_contexts=_suma("tytul_contexts"),
    streszczenie_templates=_suma("streszczenie_templates"),
    autorzy_obowiazkowi=_suma("autorzy_obowiazkowi"),
)
