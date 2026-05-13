"""Wspolne helpery dla generatorow publikacji (WC, WZ).

Wyodrebnione przed implementacja generatora Wydawnictwo_Zwarte zeby uniknac
copy-paste drift miedzy generatorami. Pola DOI, tytulow i mapping
autor->jednostka sa wspolne; OA modele rozne (osobne tabele dla WC i WZ),
wiec OA pozostaje per-generator."""

from __future__ import annotations

import random

from bpp.demo_data.names import CONTEXTS, SUBJECTS, TOPICS, TYTULY_TEMPLATES
from bpp.models import Autor, Autor_Jednostka


def make_tytul(rng: random.Random, idx: int, prefix: str = "") -> str:
    """Generuje tytul z szablonu w `names.TYTULY_TEMPLATES`.

    `prefix` (np. " Ksiazka nadrzedna" / " Rozdzial") wstawia sie po
    em-dash w "Demo —", przed wlasciwym tytulem."""
    template = rng.choice(TYTULY_TEMPLATES)
    body = template.format(
        topic=rng.choice(TOPICS),
        subject=rng.choice(SUBJECTS),
        context=rng.choice(CONTEXTS),
    )
    return f"Demo —{prefix} {body} (nr {idx})"


def make_doi(rng: random.Random, rok: int, idx: int) -> str:
    """Generuje syntetyczny DOI w formacie `10.NNNN/demo.YYYY.IDX`."""
    prefix4 = rng.randint(1000, 9999)
    return f"10.{prefix4}/demo.{rok}.{idx}"


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
