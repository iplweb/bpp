"""Czyste funkcje kompozycji nazw z motywu. Deterministyczne przy danym rng."""

from __future__ import annotations

import random

from bpp.demo_data.themes.base import Theme


def apply_prefix(nazwa: str, prefix: str) -> str:
    """Dokleja marker (np. 'Demo — ') przed nazwą; pusty prefix → bez zmian."""
    return f"{prefix}{nazwa}"


def compose_jednostka_nazwa(theme: Theme, rng: random.Random) -> str:
    """'<prefiks> <dziedzina>', np. 'Katedra Eliksirologii'."""
    prefiks = rng.choice(theme.jednostka_prefiksy)
    dziedzina = rng.choice(theme.jednostka_dziedziny)
    return f"{prefiks} {dziedzina}"


def jednostka_nazwy(theme: Theme, rng: random.Random, n: int) -> list[str]:
    """n UNIKALNYCH nazw '<prefiks> <dziedzina>' (Jednostka.nazwa ma unique=True).

    Buduje iloczyn prefiks×dziedzina i tasuje (różnorodność); cyklicznie
    pobiera, a gdy iloczyn < n, kolejne rundy dostają sufiks ' (2)', ' (3)' …
    żeby nie zderzyć się z unique constraintem — analogicznie do
    ``wydzial_nazwy`` / ``wydawca_nazwy``."""
    pula = [
        f"{prefiks} {dziedzina}"
        for prefiks in theme.jednostka_prefiksy
        for dziedzina in theme.jednostka_dziedziny
    ]
    rng.shuffle(pula)
    out: list[str] = []
    for i in range(n):
        base = pula[i % len(pula)]
        runda = i // len(pula)
        out.append(base if runda == 0 else f"{base} ({runda + 1})")
    return out


def compose_zrodlo_nazwa(theme: Theme, rng: random.Random) -> str:
    """'<prefiks> <human>', np. 'Acta Kaedwenica'."""
    prefiks = rng.choice(theme.zrodlo_prefiksy)
    human = rng.choice(theme.zrodlo_human)
    return f"{prefiks} {human}"


def wydzial_nazwy(theme: Theme, rng: random.Random, n: int) -> list[str]:
    """n UNIKALNYCH nazw 'Wydział <dziedzina>' (Wydzial.nazwa ma unique=True).

    Cykluje po puli dziedzin (shuffle dla różnorodności); gdy pula < n,
    kolejne rundy dostają sufiks ' (2)', ' (3)' … żeby nie zderzyć się z
    unique constraintem — analogicznie do ``wydawca_nazwy``."""
    pula = list(theme.wydzial_dziedziny)
    rng.shuffle(pula)
    out: list[str] = []
    for i in range(n):
        base = f"Wydział {pula[i % len(pula)]}"
        runda = i // len(pula)
        out.append(base if runda == 0 else f"{base} ({runda + 1})")
    return out


def wydawca_nazwy(theme: Theme, rng: random.Random, n: int) -> list[str]:
    """n UNIKALNYCH nazw wydawców (Wydawca.nazwa ma unique=True).

    Cykluje po puli; gdy wyczerpana, dokleja ' (Oddział K)'."""
    pula = list(theme.wydawcy)
    rng.shuffle(pula)
    out: list[str] = []
    for i in range(n):
        base = pula[i % len(pula)]
        runda = i // len(pula)
        out.append(base if runda == 0 else f"{base} (Oddział {runda + 1})")
    return out


def compose_autor(theme: Theme, rng: random.Random) -> tuple[str, str]:
    """('<imiona>', '<nazwisko>'); nazwisko nigdy puste (gwarantuje motyw)."""
    return rng.choice(theme.autor_imiona), rng.choice(theme.autor_nazwiska)


def compose_tytul(theme: Theme, rng: random.Random) -> str:
    """Treść tytułu (bez markera/idx) z szablonu × topic/subject/context."""
    template = rng.choice(theme.tytul_templates)
    return template.format(
        topic=rng.choice(theme.tytul_topics),
        subject=rng.choice(theme.tytul_subjects),
        context=rng.choice(theme.tytul_contexts),
    )


def compose_streszczenie(theme: Theme, rng: random.Random) -> str:
    """3–5 zdań z `streszczenie_templates`, placeholdery wypełnione z pul."""
    n_zdan = rng.randint(3, 5)
    zdania = []
    for _ in range(n_zdan):
        template = rng.choice(theme.streszczenie_templates)
        zdania.append(
            template.format(
                topic=rng.choice(theme.tytul_topics),
                subject=rng.choice(theme.tytul_subjects),
                context=rng.choice(theme.tytul_contexts),
            )
        )
    return " ".join(zdania)
