"""Testy systemu motywów (Theme dataclass, compose, registry)."""

import pytest

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


def _mini_theme():
    from bpp.demo_data.themes.base import Theme

    return Theme(
        key="t",
        label="T",
        uczelnia_nazwy=("Uniwersytet Testowy",),
        uczelnia_skrot="UT",
        wydzial_dziedziny=("Lekarski", "Farmaceutyczny", "Chemii"),
        jednostka_dziedziny=("Kardiologii", "Biochemii"),
        autor_imiona=("Anna", "Jan"),
        autor_nazwiska=("Kowalski", "Nowak"),
        zrodlo_human=("Medica", "Biochemica"),
        wydawcy=("Wyd. A", "Wyd. B"),
        tytul_topics=("biomarkerów",),
        tytul_subjects=("skuteczność",),
        tytul_contexts=("warunkach klinicznych",),
        streszczenie_templates=(
            "Zbadano wpływ {topic} na {subject}.",
            "Analizę przeprowadzono w {context}.",
        ),
    )


def test_compose_jednostka_uses_prefix_and_dziedzina():
    import random

    from bpp.demo_data.themes.compose import compose_jednostka_nazwa

    t = _mini_theme()
    nazwa = compose_jednostka_nazwa(t, random.Random(1))
    assert any(nazwa.startswith(p) for p in t.jednostka_prefiksy)
    assert any(nazwa.endswith(d) for d in t.jednostka_dziedziny)


def test_compose_autor_returns_pair_from_pools():
    import random

    from bpp.demo_data.themes.compose import compose_autor

    t = _mini_theme()
    imiona, nazwisko = compose_autor(t, random.Random(1))
    assert imiona in t.autor_imiona
    assert nazwisko in t.autor_nazwiska


def test_wydawca_nazwy_are_unique():
    import random

    from bpp.demo_data.themes.compose import wydawca_nazwy

    t = _mini_theme()  # pula = 2 wydawców
    nazwy = wydawca_nazwy(t, random.Random(1), 5)
    assert len(nazwy) == 5
    assert len(set(nazwy)) == 5  # unikalne mimo puli < n


def test_wydzial_nazwy_are_unique():
    """Wydzial.nazwa ma unique=True — gdy prosimy o więcej wydziałów niż jest
    dziedzin w motywie, nazwy MUSZĄ pozostać unikalne (dawniej pula była
    cyklowana bez deduplikacji → IntegrityError w bulk_create)."""
    import random

    from bpp.demo_data.themes.compose import wydzial_nazwy

    t = _mini_theme()  # pula = 3 wydziały
    nazwy = wydzial_nazwy(t, random.Random(1), 7)
    assert len(nazwy) == 7
    assert len(set(nazwy)) == 7  # unikalne mimo puli < n
    assert all(n.startswith("Wydział ") for n in nazwy)


def test_jednostka_nazwy_are_unique():
    """Jednostka.nazwa ma unique=True — nazwy MUSZĄ być unikalne nawet gdy
    liczba jednostek przekracza iloczyn prefiks×dziedzina (dawniej losowa
    kompozycja per-jednostka zderzała się → IntegrityError)."""
    import random

    from bpp.demo_data.themes.compose import jednostka_nazwy

    t = _mini_theme()  # 7 prefiksów (SHARED) × 2 dziedziny = 14 kombinacji
    nazwy = jednostka_nazwy(t, random.Random(1), 20)
    assert len(nazwy) == 20
    assert len(set(nazwy)) == 20  # unikalne mimo iloczynu < n


def test_apply_prefix():
    from bpp.demo_data.themes.compose import apply_prefix

    assert apply_prefix("Kardiologii", "Demo — ") == "Demo — Kardiologii"
    assert apply_prefix("Kardiologii", "") == "Kardiologii"


def test_compose_determinism():
    import random

    from bpp.demo_data.themes.compose import compose_jednostka_nazwa

    t = _mini_theme()
    a = compose_jednostka_nazwa(t, random.Random(42))
    b = compose_jednostka_nazwa(t, random.Random(42))
    assert a == b


def test_compose_streszczenie_fills_placeholders():
    import random

    from bpp.demo_data.themes.compose import compose_streszczenie

    t = _mini_theme()
    s = compose_streszczenie(t, random.Random(1))
    assert "{" not in s and "}" not in s  # wszystkie placeholdery wypełnione
    assert len(s) > 0


def test_registry_has_all_required_pools_nonempty():
    from bpp.demo_data.themes.base import Theme
    from bpp.demo_data.themes.registry import THEMES

    pool_fields = [
        "uczelnia_nazwy",
        "wydzial_dziedziny",
        "jednostka_dziedziny",
        "autor_imiona",
        "autor_nazwiska",
        "zrodlo_human",
        "wydawcy",
        "tytul_topics",
        "tytul_subjects",
        "tytul_contexts",
        "streszczenie_templates",
        "jednostka_prefiksy",
        "zrodlo_prefiksy",
        "tytul_templates",
    ]
    assert THEMES, "registry nie może być pusty"
    for key, theme in THEMES.items():
        assert isinstance(theme, Theme)
        assert theme.key == key
        assert theme.label
        assert theme.uczelnia_skrot
        for f in pool_fields:
            assert len(getattr(theme, f)) > 0, f"{key}.{f} puste"


def test_get_theme_known_and_unknown():
    import pytest

    from bpp.demo_data.themes.registry import get_theme

    assert get_theme("realistyczny").key == "realistyczny"
    with pytest.raises(ValueError):
        get_theme("nie-istnieje")


@pytest.mark.parametrize("key", ["lem", "wiedzmin", "harry-potter", "disney"])
def test_themed_modules_registered_and_compose(key):
    import random

    from bpp.demo_data.themes.compose import (
        compose_autor,
        compose_jednostka_nazwa,
        compose_streszczenie,
        compose_zrodlo_nazwa,
    )
    from bpp.demo_data.themes.registry import get_theme

    theme = get_theme(key)
    rng = random.Random(1)
    assert compose_jednostka_nazwa(theme, rng)
    imiona, nazwisko = compose_autor(theme, rng)
    assert imiona and nazwisko  # nazwisko nigdy puste
    assert compose_zrodlo_nazwa(theme, rng)
    s = compose_streszczenie(theme, rng)
    assert "{" not in s and "}" not in s
