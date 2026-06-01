"""Testy systemu motywów (Theme dataclass, compose, registry)."""

from bpp.demo_data.themes.base import (
    SHARED_JEDNOSTKA_PREFIKSY,
    SHARED_TYTUL_TEMPLATES,
    SHARED_ZRODLO_PREFIKSY,
    Theme,
)


def test_theme_uses_shared_defaults():
    """Theme bez podania pól strukturalnych dziedziczy stałe SHARED_*."""
    t = Theme(
        key="x",
        label="X",
        uczelnia_nazwy=("U",),
        uczelnia_skrot="U",
        wydzial_dziedziny=("A",),
        jednostka_dziedziny=("Kardiologii",),
        autor_imiona=("Jan",),
        autor_nazwiska=("Kowalski",),
        zrodlo_human=("Medica",),
        wydawcy=("Wyd. A",),
        tytul_topics=("t",),
        tytul_subjects=("s",),
        tytul_contexts=("c",),
        streszczenie_templates=("Zbadano {topic}.",),
    )
    assert t.jednostka_prefiksy == SHARED_JEDNOSTKA_PREFIKSY
    assert t.zrodlo_prefiksy == SHARED_ZRODLO_PREFIKSY
    assert t.tytul_templates == SHARED_TYTUL_TEMPLATES
    assert t.key == "x"


def test_theme_is_frozen():
    """Theme jest immutable (frozen dataclass)."""
    import dataclasses

    import pytest

    t = Theme(
        key="x",
        label="X",
        uczelnia_nazwy=("U",),
        uczelnia_skrot="U",
        wydzial_dziedziny=("A",),
        jednostka_dziedziny=("K",),
        autor_imiona=("Jan",),
        autor_nazwiska=("Nowak",),
        zrodlo_human=("M",),
        wydawcy=("W",),
        tytul_topics=("t",),
        tytul_subjects=("s",),
        tytul_contexts=("c",),
        streszczenie_templates=("X.",),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.key = "y"
