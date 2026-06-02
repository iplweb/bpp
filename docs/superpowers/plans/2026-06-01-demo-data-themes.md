# Motywy (THEMES) + streszczenia dla `create_demo_data` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rozszerzyć istniejący generator `bpp.demo_data` o wymienialne motywy (realistyczny, lem, wiedzmin, harry-potter, disney) dostarczające nazwy dla wszystkich encji, realistyczne nazewnictwo przez kompozycję, oraz generator tematycznych streszczeń prac.

**Architecture:** Nowy podpakiet `bpp/demo_data/themes/` z `Theme` (frozen dataclass `kw_only`) jako paczką treści, `compose.py` (czyste funkcje składające nazwy z `rng`), `registry.py` (dict + `get_theme`). Istniejące generatory dostają parametry `theme` + `prefix` zamiast hardkodów. Nowy `generators/streszczenia.py` tworzy wiersze `Wydawnictwo_*_Streszczenie`. Wszystko deterministyczne po `--seed`, cleanup po PK z manifestu bez zmian.

**Tech Stack:** Python ≥3.10, Django, pytest + `model_bakery`, `bulk_create`, `random.Random` (RNG per-run, nie globalny).

**Spec:** `docs/superpowers/specs/2026-06-01-demo-data-themes-design.md`

**Konwencje repo (KRYTYCZNE):**
- Wszystkie komendy Pythona z prefiksem `uv run`. NIGDY `python` wprost.
- Max długość linii: 88 znaków (ruff).
- Testy: pytest, standalone functions, `@pytest.mark.django_db(transaction=True)`, `model_bakery.baker.make`.
- Po zmianach: `ruff format .` + `ruff check .` (NIE `--fix`). `pre-commit` bez argumentów.
- Praca toczy się w worktree `~/Programowanie/bpp-demo-themes` (branch `worktree-demo-themes`).
- Uruchamianie testów demo: `uv run pytest src/bpp/tests/test_demo_data/ -p no:cacheprovider`

---

## Task 1: `themes/base.py` — `Theme` dataclass + stałe współdzielone

**Files:**
- Create: `src/bpp/demo_data/themes/__init__.py` (pusty)
- Create: `src/bpp/demo_data/themes/base.py`
- Test: `src/bpp/tests/test_demo_data/test_themes.py`

- [ ] **Step 1: Utwórz pusty `__init__.py`**

```bash
mkdir -p src/bpp/demo_data/themes
touch src/bpp/demo_data/themes/__init__.py
```

- [ ] **Step 2: Write failing test**

Utwórz `src/bpp/tests/test_demo_data/test_themes.py`:

```python
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
        key="x", label="X", uczelnia_nazwy=("U",), uczelnia_skrot="U",
        wydzial_dziedziny=("A",), jednostka_dziedziny=("K",),
        autor_imiona=("Jan",), autor_nazwiska=("Nowak",),
        zrodlo_human=("M",), wydawcy=("W",), tytul_topics=("t",),
        tytul_subjects=("s",), tytul_contexts=("c",),
        streszczenie_templates=("X.",),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.key = "y"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_themes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bpp.demo_data.themes.base'`

- [ ] **Step 4: Write `base.py`**

Utwórz `src/bpp/demo_data/themes/base.py`:

```python
"""Theme — paczka treści dla generatora demo data (dane, zero logiki).

Pola flavorowane są wymagane; pola strukturalne (prefiksy jednostek/źródeł,
szablony tytułów) mają domyślne = stałe SHARED_*. `kw_only=True` pozwala
mieszać pola z domyślną i bez domyślnej w dowolnej kolejności.
"""

from __future__ import annotations

from dataclasses import dataclass

SHARED_JEDNOSTKA_PREFIKSY: tuple[str, ...] = (
    "Katedra",
    "Zakład",
    "Klinika",
    "Katedra i Klinika",
    "Katedra i Zakład",
    "Instytut",
    "Pracownia",
)

SHARED_ZRODLO_PREFIKSY: tuple[str, ...] = (
    "Acta",
    "Annales",
    "Folia",
    "Roczniki",
    "Przegląd",
    "Zeszyty Naukowe",
    "Studia",
)

SHARED_TYTUL_TEMPLATES: tuple[str, ...] = (
    "Analiza wpływu {topic} na {subject} w {context}",
    "Badania {topic} w kontekście {subject}",
    "Wpływ {topic} na {subject}",
    "{topic}: studium przypadku {subject}",
    "Metodologia {topic} w {context}",
    "Modelowanie {topic} z wykorzystaniem {subject}",
    "Perspektywy rozwoju {topic} w {context}",
    "{topic} jako narzędzie {subject}",
    "Optymalizacja {topic} w {context}",
    "Przegląd literatury: {topic} a {subject}",
)


@dataclass(frozen=True, kw_only=True)
class Theme:
    key: str
    label: str
    # Uczelnia (singleton — bierzemy [0] deterministycznie):
    uczelnia_nazwy: tuple[str, ...]
    uczelnia_skrot: str
    # Wydział: "Wydział <dziedzina>"
    wydzial_dziedziny: tuple[str, ...]
    # Jednostka: "<prefiks> <dziedzina>"
    jednostka_dziedziny: tuple[str, ...]
    # Autor: "<imiona> <nazwisko>"
    autor_imiona: tuple[str, ...]
    autor_nazwiska: tuple[str, ...]
    # Źródło: "<prefiks> <human>"
    zrodlo_human: tuple[str, ...]
    # Wydawcy: pełne nazwy
    wydawcy: tuple[str, ...]
    # Tytuły:
    tytul_topics: tuple[str, ...]
    tytul_subjects: tuple[str, ...]
    tytul_contexts: tuple[str, ...]
    # Streszczenia ({topic}/{subject}/{context} z pól tytułowych):
    streszczenie_templates: tuple[str, ...]
    # Pola strukturalne z domyślnymi SHARED_*:
    jednostka_prefiksy: tuple[str, ...] = SHARED_JEDNOSTKA_PREFIKSY
    zrodlo_prefiksy: tuple[str, ...] = SHARED_ZRODLO_PREFIKSY
    tytul_templates: tuple[str, ...] = SHARED_TYTUL_TEMPLATES
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_themes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/bpp/demo_data/themes/__init__.py src/bpp/demo_data/themes/base.py \
    src/bpp/tests/test_demo_data/test_themes.py
git commit -m "feat(demo-data): Theme dataclass + stałe SHARED_* (base motywów)"
```

---

## Task 2: `themes/compose.py` — helpery kompozycji nazw

**Files:**
- Create: `src/bpp/demo_data/themes/compose.py`
- Test: `src/bpp/tests/test_demo_data/test_themes.py` (dopisz)

- [ ] **Step 1: Write failing test (dopisz na końcu `test_themes.py`)**

```python
def _mini_theme():
    from bpp.demo_data.themes.base import Theme

    return Theme(
        key="t", label="T",
        uczelnia_nazwy=("Uniwersytet Testowy",), uczelnia_skrot="UT",
        wydzial_dziedziny=("Lekarski", "Farmaceutyczny", "Chemii"),
        jednostka_dziedziny=("Kardiologii", "Biochemii"),
        autor_imiona=("Anna", "Jan"), autor_nazwiska=("Kowalski", "Nowak"),
        zrodlo_human=("Medica", "Biochemica"),
        wydawcy=("Wyd. A", "Wyd. B"),
        tytul_topics=("biomarkerów",), tytul_subjects=("skuteczność",),
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_themes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bpp.demo_data.themes.compose'`

- [ ] **Step 3: Write `compose.py`**

Utwórz `src/bpp/demo_data/themes/compose.py`:

```python
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


def compose_zrodlo_nazwa(theme: Theme, rng: random.Random) -> str:
    """'<prefiks> <human>', np. 'Acta Kaedwenica'."""
    prefiks = rng.choice(theme.zrodlo_prefiksy)
    human = rng.choice(theme.zrodlo_human)
    return f"{prefiks} {human}"


def wydzial_nazwy(theme: Theme, rng: random.Random, n: int) -> list[str]:
    """n nazw 'Wydział <dziedzina>'; shuffle+cycle dla różnorodności."""
    dziedziny = list(theme.wydzial_dziedziny)
    rng.shuffle(dziedziny)
    dziedziny = (dziedziny * ((n // len(dziedziny)) + 1))[:n]
    return [f"Wydział {d}" for d in dziedziny]


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_themes.py -v`
Expected: PASS (wszystkie z Task 1 i 2)

- [ ] **Step 5: Commit**

```bash
git add src/bpp/demo_data/themes/compose.py src/bpp/tests/test_demo_data/test_themes.py
git commit -m "feat(demo-data): helpery kompozycji nazw z motywu (compose.py)"
```

---

## Task 3: `themes/realistyczny.py` + `registry.py` (przeniesienie `names.py`)

**Files:**
- Create: `src/bpp/demo_data/themes/realistyczny.py`
- Create: `src/bpp/demo_data/themes/registry.py`
- Delete: `src/bpp/demo_data/names.py` (po przeniesieniu treści — w Task 5 odłączamy ostatni import)
- Test: `src/bpp/tests/test_demo_data/test_themes.py` (dopisz)

- [ ] **Step 1: Write failing test (dopisz)**

```python
def test_registry_has_all_required_pools_nonempty():
    from bpp.demo_data.themes.base import Theme
    from bpp.demo_data.themes.registry import THEMES

    pool_fields = [
        "uczelnia_nazwy", "wydzial_dziedziny", "jednostka_dziedziny",
        "autor_imiona", "autor_nazwiska", "zrodlo_human", "wydawcy",
        "tytul_topics", "tytul_subjects", "tytul_contexts",
        "streszczenie_templates", "jednostka_prefiksy", "zrodlo_prefiksy",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_themes.py::test_get_theme_known_and_unknown -v`
Expected: FAIL — `ModuleNotFoundError: ...themes.registry`

- [ ] **Step 3: Write `realistyczny.py`** (przenosi pule z `names.py` + dodaje nowe)

Utwórz `src/bpp/demo_data/themes/realistyczny.py`. Skopiuj `IMIONA_POL`, `NAZWISKA_POL`, `KIERUNKI_POL`, `TOPICS`, `SUBJECTS`, `CONTEXTS` z obecnego `src/bpp/demo_data/names.py` (1:1) i dodaj nowe pule. Struktura:

```python
"""Motyw 'realistyczny' — polskie dane akademickie (domyślny, bez żartu)."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme

# --- przeniesione z dawnego names.py (skopiuj 1:1 zawartość krotek) ---
IMIONA_POL = (
    "Anna", "Maria", "Katarzyna",  # ... CAŁA lista z names.py ...
)
NAZWISKA_POL = (
    "Nowak", "Kowalski", "Wiśniewski",  # ... CAŁA lista z names.py ...
)
KIERUNKI_POL = (
    "Lekarski", "Lekarsko-Dentystyczny", "Farmaceutyczny",  # ... CAŁA lista ...
)
TOPICS = (
    "metod numerycznych", "algorytmów uczenia maszynowego",  # ... CAŁA lista ...
)
SUBJECTS = (
    "skuteczność leczenia", "jakość życia pacjentów",  # ... CAŁA lista ...
)
CONTEXTS = (
    "warunkach klinicznych", "środowisku laboratoryjnym",  # ... CAŁA lista ...
)

# --- nowe pule realistyczne ---
JEDNOSTKA_DZIEDZINY = (
    "Kardiologii", "Biochemii", "Mikrobiologii Lekarskiej",
    "Anatomii Prawidłowej", "Genetyki Molekularnej", "Chirurgii Ogólnej",
    "Farmakologii", "Patomorfologii", "Neurologii", "Pediatrii",
    "Fizjologii", "Immunologii", "Histologii", "Onkologii", "Radiologii",
)
ZRODLO_HUMAN = (
    "Medica Polonica", "Biochemica", "Clinica", "Neurologica",
    "Chirurgica", "Oncologica", "Pharmaceutica", "Microbiologica",
    "Academiae Medicae", "Diagnostica",
)
WYDAWCY = (
    "Wydawnictwo Naukowe PWN", "Wydawnictwo Lekarskie PZWL",
    "Wydawnictwo Uniwersyteckie", "Oficyna Wydawnicza Scholar",
    "Wydawnictwo Naukowe UAM", "Elsevier Urban & Partner",
    "Wydawnictwo Czelej", "Termedia Wydawnictwa Medyczne",
)
STRESZCZENIE_TEMPLATES = (
    "W niniejszej pracy zbadano wpływ {topic} na {subject}.",
    "Analizę przeprowadzono w {context}, z uwzględnieniem {topic}.",
    "Wyniki wskazują na istotny związek {topic} z {subject}.",
    "Celem badania była ocena {topic} w odniesieniu do {subject}.",
    "Materiał i metody obejmowały {topic} w {context}.",
    "Wnioski potwierdzają znaczenie {topic} dla {subject}.",
)

REALISTYCZNY = Theme(
    key="realistyczny",
    label="Realistyczny (polski akademicki)",
    uczelnia_nazwy=("Uniwersytet Przykładowy", "Akademia Nauk Stosowanych"),
    uczelnia_skrot="UP",
    wydzial_dziedziny=KIERUNKI_POL,
    jednostka_dziedziny=JEDNOSTKA_DZIEDZINY,
    autor_imiona=IMIONA_POL,
    autor_nazwiska=NAZWISKA_POL,
    zrodlo_human=ZRODLO_HUMAN,
    wydawcy=WYDAWCY,
    tytul_topics=TOPICS,
    tytul_subjects=SUBJECTS,
    tytul_contexts=CONTEXTS,
    streszczenie_templates=STRESZCZENIE_TEMPLATES,
)
```

> **UWAGA:** w miejscach `# ... CAŁA lista ...` wklej dokładną, pełną
> zawartość odpowiednich krotek z `src/bpp/demo_data/names.py` (otwórz plik
> i skopiuj wszystkie elementy). Nie skracaj.

- [ ] **Step 4: Write `registry.py`**

Utwórz `src/bpp/demo_data/themes/registry.py`:

```python
"""Rejestr motywów: klucz CLI → Theme."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.realistyczny import REALISTYCZNY

THEMES: dict[str, Theme] = {t.key: t for t in (REALISTYCZNY,)}


def get_theme(key: str) -> Theme:
    try:
        return THEMES[key]
    except KeyError:
        raise ValueError(
            f"Nieznany motyw '{key}'. Dostępne: {sorted(THEMES)}"
        ) from None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_themes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/bpp/demo_data/themes/realistyczny.py \
    src/bpp/demo_data/themes/registry.py \
    src/bpp/tests/test_demo_data/test_themes.py
git commit -m "feat(demo-data): motyw realistyczny + registry get_theme"
```

---

## Task 4: Refactor generatorów encji na `theme` + `prefix`

Generatory: `uczelnia`, `wydzialy`, `jednostki`, `autorzy`, `zrodla`, `wydawcy`.
Najpierw aktualizujemy testy (theme-aware), potem implementację.

**Files:**
- Modify: `src/bpp/demo_data/generators/uczelnia.py`
- Modify: `src/bpp/demo_data/generators/wydzialy.py`
- Modify: `src/bpp/demo_data/generators/jednostki.py`
- Modify: `src/bpp/demo_data/generators/autorzy.py`
- Modify: `src/bpp/demo_data/generators/zrodla.py`
- Modify: `src/bpp/demo_data/generators/wydawcy.py`
- Test: `test_generator_uczelnia.py`, `test_generator_wydzialy_jednostki.py`, `test_generator_autorzy.py`, `test_generator_zrodla_wydawcy.py`

- [ ] **Step 1: Zaktualizuj testy na theme-aware**

W `test_generator_autorzy.py`:
- W `jednostki_fixture` dodaj `theme=REALISTYCZNY, prefix="Demo — "` do wywołań `create_wydzialy` i `create_jednostki`; dodaj import `from bpp.demo_data.themes.registry import get_theme` → `REALISTYCZNY = get_theme("realistyczny")`.
- Każde `create_autorzy(...)` dostaje `theme=REALISTYCZNY`.
- `test_autorzy_have_polish_names`: zamień import i asercje:

```python
@pytest.mark.django_db(transaction=True)
def test_autorzy_have_polish_names(jednostki_fixture, tmp_manifest_path):
    from bpp.demo_data.themes.registry import get_theme

    theme = get_theme("realistyczny")
    m, jednostki = jednostki_fixture
    autorzy = create_autorzy(
        n=5, jednostki=jednostki, theme=theme, manifest=m,
        rng=random.Random(3), batch_size=100, disable_progress=True,
    )
    for a in autorzy:
        assert a.imiona in theme.autor_imiona
        assert a.nazwisko in theme.autor_nazwiska
```

W `test_generator_wydzialy_jednostki.py`:
- Dodaj `from bpp.demo_data.themes.registry import get_theme` i `theme=get_theme("realistyczny")`, `prefix="Demo — "` do `create_wydzialy`/`create_jednostki`.
- `test_create_wydzialy_creates_n_records`: zostaw `assert w.nazwa.startswith("Demo")` (marker domyślnie ON), DODAJ `assert "Wydział" in w.nazwa`.
- `test_create_jednostki_per_wydzial`: DODAJ asercję realizmu:

```python
    from bpp.demo_data.themes.base import SHARED_JEDNOSTKA_PREFIKSY
    for j in jednostki:
        # marker + realistyczny prefiks jednostki, NIE "Jednostka N"
        assert j.nazwa.startswith("Demo — ")
        bez_markera = j.nazwa[len("Demo — "):]
        assert any(bez_markera.startswith(p) for p in SHARED_JEDNOSTKA_PREFIKSY)
        assert "Jednostka " not in j.nazwa
```

W `test_generator_zrodla_wydawcy.py`:
- Dodaj `theme=get_theme("realistyczny"), prefix="Demo — "` do `create_zrodla`/`create_wydawcy`.
- Zostaw `startswith("Demo —")`; DODAJ do `test_create_zrodla`: `assert any(z.nazwa[len("Demo — "):].startswith(p) for p in ("Acta","Annales","Folia","Roczniki","Przegląd","Zeszyty Naukowe","Studia"))`.

W `test_generator_uczelnia.py`:
- `ensure_uczelnia(m)` → `ensure_uczelnia(m, theme=get_theme("realistyczny"), prefix="Demo — ")`. Zostaw `assert uczelnia.nazwa.startswith("Demo")`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_autorzy.py src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py src/bpp/tests/test_demo_data/test_generator_zrodla_wydawcy.py src/bpp/tests/test_demo_data/test_generator_uczelnia.py -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'theme'`

- [ ] **Step 3: Refactor `uczelnia.py`**

```python
"""Generator Uczelni (singleton) dla demo_data."""

from __future__ import annotations

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix
from bpp.models import Uczelnia


def ensure_uczelnia(manifest: Manifest, *, theme: Theme, prefix: str = "") -> Uczelnia:
    """Zwraca singleton Uczelni. Jeśli brak — tworzy z nazwą motywu i wpisuje
    do manifestu z flagą `created_by_demo`."""
    existing = Uczelnia.objects.first()
    if existing is not None:
        return existing

    nazwa = apply_prefix(theme.uczelnia_nazwy[0], prefix)
    uczelnia = Uczelnia.objects.create(
        nazwa=nazwa,
        skrot=theme.uczelnia_skrot,
        nazwa_dopelniacz_field=nazwa,
    )
    manifest.append("bpp.Uczelnia", [uczelnia.pk], extra={"created_by_demo": True})
    return uczelnia
```

- [ ] **Step 4: Refactor `wydzialy.py`**

Zmień sygnaturę i ciało (usuń import `KIERUNKI_POL`, użyj `wydzial_nazwy`):

```python
"""Generator Wydzialow."""

from __future__ import annotations

import random

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, wydzial_nazwy
from bpp.models import Uczelnia, Wydzial


def create_wydzialy(
    *,
    n: int,
    uczelnia: Uczelnia,
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydzial]:
    nazwy = wydzial_nazwy(theme, rng, n)
    objs = [
        Wydzial(
            uczelnia=uczelnia,
            nazwa=apply_prefix(nazwy[i], prefix),
            skrot=f"DW{i + 1}",
            skrot_nazwy=f"DW{i + 1}",
            kolejnosc=i,
        )
        for i in range(n)
    ]

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Wydziały",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydzial] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Wydzial.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydzial", [w.pk for w in chunk])
        manifest.save()
    return created
```

- [ ] **Step 5: Refactor `jednostki.py`**

Dodaj parametry `theme`, `prefix`; zamień `nazwa=f"Demo — Jednostka {w_idx}-{j_idx}"` na kompozycję. Skrót zostaje indeksowy:

```python
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, compose_jednostka_nazwa
```

Sygnatura `create_jednostki(*, per_wydzial, wydzialy, uczelnia, theme, manifest, rng, prefix="", batch_size=500, disable_progress=False)`. Wewnątrz pętli:

```python
            objs.append(
                Jednostka(
                    uczelnia=uczelnia,
                    wydzial=wydzial,
                    nazwa=apply_prefix(compose_jednostka_nazwa(theme, rng), prefix),
                    skrot=f"DJ{w_idx}-{j_idx}",
                    rodzaj_jednostki=Jednostka.RODZAJ_JEDNOSTKI.NORMALNA,
                    lft=0, rght=0, tree_id=0, level=0,
                )
            )
```

(Reszta — bulk_create, `Jednostka.objects.rebuild()`, manifest — bez zmian.)

- [ ] **Step 6: Refactor `autorzy.py`**

Usuń `from bpp.demo_data.names import IMIONA_POL, NAZWISKA_POL`; dodaj:

```python
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import compose_autor
```

Dodaj param `theme: Theme` do `create_autorzy` (po `jednostki`). W pętli zamień:

```python
    for i in range(n):
        imiona, nazwisko = compose_autor(theme, rng)
        slug_value = slugify(f"{imiona} {nazwisko}-demo-{i + 1}")
        autorzy_objs.append(
            Autor(
                imiona=imiona,
                nazwisko=nazwisko,
                sort=_make_sort_key(nazwisko, imiona),
                slug=slug_value,
            )
        )
```

- [ ] **Step 7: Refactor `zrodla.py`**

Dodaj `theme`, `prefix`; zamień `nazwa = f"Demo — Czasopismo {i + 1}"`:

```python
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, compose_zrodlo_nazwa
```

Sygnatura `create_zrodla(*, n, theme, manifest, rng, prefix="", batch_size=500, disable_progress=False)`. W pętli:

```python
    for i in range(n):
        nazwa = apply_prefix(compose_zrodlo_nazwa(theme, rng), prefix)
        objs.append(
            Zrodlo(
                nazwa=nazwa,
                skrot=f"DC{i + 1}",
                rodzaj=rng.choice(rodzaje),
                issn=_synthetic_issn(rng),
                slug=slugify(f"{nazwa}-demo-{i + 1}"),
            )
        )
```

- [ ] **Step 8: Refactor `wydawcy.py`**

Dodaj `theme`, `prefix`; użyj `wydawca_nazwy` (unikalność):

```python
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import apply_prefix, wydawca_nazwy
```

Sygnatura `create_wydawcy(*, n, theme, manifest, rng, prefix="", batch_size=500, disable_progress=False)`:

```python
    nazwy = wydawca_nazwy(theme, rng, n)
    objs = [Wydawca(nazwa=apply_prefix(nazwy[i], prefix)) for i in range(n)]
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_autorzy.py src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py src/bpp/tests/test_demo_data/test_generator_zrodla_wydawcy.py src/bpp/tests/test_demo_data/test_generator_uczelnia.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/bpp/demo_data/generators/ src/bpp/tests/test_demo_data/
git commit -m "refactor(demo-data): generatory encji na theme + prefix (realistyczne nazwy)"
```

---

## Task 5: Refactor generatorów publikacji + usunięcie `names.py`

**Files:**
- Modify: `src/bpp/demo_data/generators/_publikacje_common.py`
- Modify: `src/bpp/demo_data/generators/wydawnictwa_ciagle.py`
- Modify: `src/bpp/demo_data/generators/wydawnictwa_zwarte.py`
- Delete: `src/bpp/demo_data/names.py`
- Test: `test_publikacje` (jeśli istnieje) + `test_command_create.py`

- [ ] **Step 1: Refactor `make_tytul` w `_publikacje_common.py`**

Usuń import `from bpp.demo_data.names import CONTEXTS, SUBJECTS, TOPICS, TYTULY_TEMPLATES`. Dodaj `from bpp.demo_data.themes.base import Theme` i `from bpp.demo_data.themes.compose import compose_tytul`. Zamień `make_tytul`:

```python
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
```

- [ ] **Step 2: Refactor `wydawnictwa_ciagle.py`**

`_build_praca` dostaje `theme` + `marker`; `tytul = make_tytul(theme, rng, idx, marker=marker)`. `create_wc` dostaje `theme: Theme` (po `zrodla`) i `prefix: str = ""`; przekazuje do `_build_praca(... theme=theme, marker=prefix)`. Zmień:

```python
def _build_praca(*, rng, idx, rok, zrodla, s, theme, marker=""):
    tytul = make_tytul(theme, rng, idx, marker=marker)
    ...
```

i w `create_wc` listę składania prac:

```python
    prace = [
        _build_praca(
            rng=rng, idx=i + 1, rok=rng.choice(lata), zrodla=zrodla, s=s,
            theme=theme, marker=prefix,
        )
        for i in range(n)
    ]
```

- [ ] **Step 3: Refactor `wydawnictwa_zwarte.py`**

`_build_praca` zmień parametr `prefix` (rola) → `rola`, dodaj `theme` + `marker`:

```python
def _build_praca(*, rng, idx, rok, wydawcy, s, theme, marker="", rola=""):
    tytul = make_tytul(theme, rng, idx, marker=marker, rola=rola)
    ...
```

`create_wz` dostaje `theme: Theme` (po `wydawcy`) i `prefix: str = ""`. Wszystkie wywołania `_build_praca` dostają `theme=theme, marker=prefix`; tam gdzie był `prefix=" Książka nadrzędna"` → `rola="Książka nadrzędna"`, gdzie `prefix=" Rozdział"` → `rola="Rozdział"`.

- [ ] **Step 4: Usuń `names.py`**

```bash
git rm src/bpp/demo_data/names.py
```

Sprawdź brak innych importów:

Run: `grep -rn "demo_data.names\|demo_data import names" src/ || echo "BRAK importów — OK"`
Expected: `BRAK importów — OK`

- [ ] **Step 5: Run tests (command smoke jeszcze nie zna theme → na razie pominąć command; sprawdź import-time)**

Run: `uv run python -c "import bpp.demo_data.orchestrator"`
Expected: błąd dot. `theme` w orchestratorze pojawi się w Task 8; tu sprawdzamy tylko że generatory się importują:

Run: `uv run python -c "from bpp.demo_data.generators import wydawnictwa_ciagle, wydawnictwa_zwarte, _publikacje_common; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add -A src/bpp/demo_data/generators/ src/bpp/demo_data/names.py
git commit -m "refactor(demo-data): tytuły prac z motywu + konfigurowalny marker; usuń names.py"
```

---

## Task 6: Cztery motywy tematyczne + rejestracja

**Files:**
- Create: `src/bpp/demo_data/themes/lem.py`
- Create: `src/bpp/demo_data/themes/wiedzmin.py`
- Create: `src/bpp/demo_data/themes/harry_potter.py`
- Create: `src/bpp/demo_data/themes/disney.py`
- Modify: `src/bpp/demo_data/themes/registry.py`
- Test: `src/bpp/tests/test_demo_data/test_themes.py` (dopisz)

- [ ] **Step 1: Write failing test (dopisz)**

```python
import pytest


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest "src/bpp/tests/test_demo_data/test_themes.py::test_themed_modules_registered_and_compose" -v`
Expected: FAIL — `ValueError: Nieznany motyw 'lem'...`

- [ ] **Step 3: Write `lem.py`**

```python
"""Motyw 'lem' — Stanisław Lem."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme

LEM = Theme(
    key="lem",
    label="Stanisław Lem",
    uczelnia_nazwy=(
        "Instytut Badań Kosmicznych im. Ijona Tichego",
        "Wyższa Szkoła Cybernetyki Solaryjskiej",
    ),
    uczelnia_skrot="IBK",
    wydzial_dziedziny=(
        "Kosmonautyki", "Cybernetyki", "Solarystyki", "Robotyki",
        "Futurologii", "Sepulkologii", "Astronautyki Stosowanej",
    ),
    jednostka_dziedziny=(
        "Solarystyki", "Robotyki Trurla", "Sepulkologii", "Bystrzochronu",
        "Cyberiady Porównawczej", "Kosmogonii Eksperymentalnej",
        "Teorii Sepulek", "Bionicznej Inżynierii Pożytecznej",
    ),
    autor_imiona=(
        "Ijon", "Kris", "Hal", "Pirx", "Trurl", "Klapaucjusz", "Snaut",
        "Rohan", "Adam", "Konstanty",
    ),
    autor_nazwiska=(
        "Tichy", "Kelvin", "Bregg", "Sartorius", "Horpach", "Berg",
        "Gibarian", "Maartens",
    ),
    zrodlo_human=(
        "Solarystyczne", "Cybernetyczne", "Sepulkarne", "Astronautyczne",
        "Kosmogoniczne", "Futurologiczne",
    ),
    wydawcy=(
        "Wydawnictwo Solaris", "Oficyna Kosmiczna Tichego",
        "Dom Wydawniczy Eden", "Wydawnictwo Cyberiada",
    ),
    tytul_topics=(
        "podróży międzygwiezdnych", "sepulek", "robotów Trurla",
        "oceanu Solaris", "cybernetyki stosowanej", "bystrzochronu",
        "konstruktorów", "wypraw Pirxa",
    ),
    tytul_subjects=(
        "stabilność psychiki kosmonauty", "skuteczność sepulenia",
        "wydajność robotów", "bezpieczeństwo lotów", "tolerancję mutacji",
    ),
    tytul_contexts=(
        "warunkach kosmicznych", "stacji orbitalnej Solaris",
        "próżni międzygwiezdnej", "modelu cybernetycznym",
        "wyprawie badawczej",
    ),
    streszczenie_templates=(
        "W pracy zbadano wpływ {topic} na {subject}.",
        "Eksperyment przeprowadzono w {context}.",
        "Wyniki rzucają nowe światło na zagadnienie {topic}.",
        "Konstruktorzy wykazali zależność {topic} od {subject}.",
        "Obserwacje w {context} potwierdzają tezę o {topic}.",
    ),
)
```

- [ ] **Step 4: Write `wiedzmin.py`**

```python
"""Motyw 'wiedzmin' — Wiedźmin (saga A. Sapkowskiego)."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme

WIEDZMIN = Theme(
    key="wiedzmin",
    label="Wiedźmin",
    uczelnia_nazwy=(
        "Akademia Wiedźmińska w Kaer Morhen",
        "Uniwersytet w Oxenfurcie",
    ),
    uczelnia_skrot="AKM",
    wydzial_dziedziny=(
        "Wiedźmiński", "Magii i Eliksirów", "Bestiariuszu", "Znaków",
        "Szermierki", "Zielarstwa",
    ),
    jednostka_dziedziny=(
        "Eliksirologii", "Bestiariuszu Porównawczego", "Znaków i Gestów",
        "Szlaku Wiedźmińskiego", "Mutacji", "Zielarstwa Wiedźmińskiego",
        "Toksykologii Stosowanej", "Szermierki",
    ),
    autor_imiona=(
        "Geralt", "Yennefer", "Ciri", "Jaskier", "Vesemir", "Triss",
        "Lambert", "Eskel", "Regis", "Filippa", "Cahir", "Milva",
    ),
    autor_nazwiska=(
        "z Rivii", "z Vengerbergu", "z Cintry", "Merigold", "z Kaer Morhen",
        "z Oxenfurtu", "z Aretuzy", "z Novigradu",
    ),
    zrodlo_human=(
        "Kaedwenica", "Wiedźmińska", "Novigradzka", "Temerska",
        "Aretuzańska", "Oxenfurcka",
    ),
    wydawcy=(
        "Wydawnictwo Kaer Morhen", "Oficyna Oxenfurcka",
        "Dom Wydawniczy Novigrad", "Wydawnictwo Aretuza",
    ),
    tytul_topics=(
        "eliksirów wiedźmińskich", "mutacji", "bestii", "znaków",
        "szlaku wiedźmińskiego", "toksyn", "potworów", "mieczy srebrnych",
    ),
    tytul_subjects=(
        "skuteczność polowania", "tolerancję eliksirów", "siłę znaków",
        "regenerację po mutacji", "rozpoznawanie bestii",
    ),
    tytul_contexts=(
        "warunkach Kaer Morhen", "lochach Novigradu", "puszczy Brokilon",
        "badaniu terenowym", "laboratorium aretuzańskim",
    ),
    streszczenie_templates=(
        "Zbadano skuteczność {topic} w odniesieniu do {subject}.",
        "Obserwacje terenowe przeprowadzono w {context}.",
        "Wyniki potwierdzają związek {topic} z {subject}.",
        "Mistrzowie szlaku wykazali wpływ {topic} na {subject}.",
        "Analiza w {context} rzuca światło na zagadnienie {topic}.",
    ),
)
```

- [ ] **Step 5: Write `harry_potter.py`**

```python
"""Motyw 'harry-potter' — uniwersum Harry'ego Pottera."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme

HARRY_POTTER = Theme(
    key="harry-potter",
    label="Harry Potter",
    uczelnia_nazwy=(
        "Hogwart — Szkoła Magii i Czarodziejstwa",
        "Akademia Magii Beauxbatons",
    ),
    uczelnia_skrot="HSM",
    wydzial_dziedziny=(
        "Magii", "Eliksirów", "Transmutacji", "Obrony przed Czarną Magią",
        "Zielarstwa", "Zaklęć",
    ),
    jednostka_dziedziny=(
        "Eliksirów", "Transmutacji", "Obrony przed Czarną Magią",
        "Zielarstwa", "Numerologii", "Zaklęć",
        "Opieki nad Magicznymi Stworzeniami", "Wróżbiarstwa",
    ),
    autor_imiona=(
        "Harry", "Hermiona", "Ron", "Albus", "Severus", "Minerwa",
        "Rubeus", "Draco", "Luna", "Neville", "Ginny", "Sybilla",
    ),
    autor_nazwiska=(
        "Potter", "Granger", "Weasley", "Dumbledore", "Snape",
        "McGonagall", "Hagrid", "Malfoy", "Lovegood", "Longbottom",
    ),
    zrodlo_human=(
        "Hogvartensia", "Magiczne", "Czarodziejskie", "Eliksirologiczne",
        "Transmutacyjne",
    ),
    wydawcy=(
        "Oficyna Hogwart Press", "Wydawnictwo Esy i Floresy",
        "Wydawnictwo Ministerstwa Magii", "Dom Wydawniczy Hogsmeade",
    ),
    tytul_topics=(
        "eliksirów", "zaklęć obronnych", "transmutacji",
        "magicznych stworzeń", "wróżbiarstwa", "numerologii",
        "ziół magicznych", "różdżek",
    ),
    tytul_subjects=(
        "skuteczność zaklęcia", "trwałość eliksiru", "siłę różdżki",
        "odporność na klątwy", "precyzję transmutacji",
    ),
    tytul_contexts=(
        "warunkach Hogwartu", "lochach Slytherinu", "Zakazanym Lesie",
        "klasie eliksirów", "badaniu w Hogsmeade",
    ),
    streszczenie_templates=(
        "Zbadano wpływ {topic} na {subject}.",
        "Doświadczenie przeprowadzono w {context}.",
        "Wyniki dowodzą zależności {topic} od {subject}.",
        "Mistrzowie magii wykazali rolę {topic} dla {subject}.",
        "Obserwacje w {context} potwierdzają hipotezę o {topic}.",
    ),
)
```

- [ ] **Step 6: Write `disney.py`**

```python
"""Motyw 'disney' — klasyczne postacie Disneya (placeholdery demo)."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme

DISNEY = Theme(
    key="disney",
    label="Disney",
    uczelnia_nazwy=(
        "Uniwersytet Disneya",
        "Akademia Magicznego Królestwa",
    ),
    uczelnia_skrot="UMK",
    wydzial_dziedziny=(
        "Animacji", "Magii Królestwa", "Przygód", "Baśni", "Muzyki",
    ),
    jednostka_dziedziny=(
        "Animacji Klasycznej", "Magii Królestwa", "Baśni Porównawczych",
        "Przygód Morskich", "Latających Dywanów", "Pieśni i Tańca",
    ),
    autor_imiona=(
        "Miki", "Donald", "Sknerus", "Goofy", "Pluto", "Daisy",
        "Elsa", "Anna", "Ariel", "Belle", "Mulan", "Simba", "Aladyn",
    ),
    # nazwiska NIGDY puste — jednoimienne postacie dostają przydomek:
    autor_nazwiska=(
        "Mysz", "Kaczor", "McKwacz", "z Arendelle", "Syrenka", "Lew",
        "z Krainy Lodu", "z Agrabah",
    ),
    zrodlo_human=(
        "Magicznego Królestwa", "Disnejowskie", "Animowane", "Baśniowe",
    ),
    wydawcy=(
        "Disney Academic Press", "Wydawnictwo Magicznego Królestwa",
        "Oficyna Myszki Miki", "Dom Wydawniczy Arendelle",
    ),
    tytul_topics=(
        "animacji klasycznej", "magii królestwa", "baśni", "przygód morskich",
        "pieśni królestwa", "latających dywanów",
    ),
    tytul_subjects=(
        "skuteczność czaru", "trwałość magii", "siłę przyjaźni",
        "tempo animacji", "rozpoznawalność postaci",
    ),
    tytul_contexts=(
        "warunkach królestwa", "zamku Arendelle", "podwodnym świecie",
        "studiu animacji", "magicznej krainie",
    ),
    streszczenie_templates=(
        "Zbadano wpływ {topic} na {subject}.",
        "Badanie przeprowadzono w {context}.",
        "Wyniki ukazują związek {topic} z {subject}.",
        "Bohaterowie królestwa wykazali rolę {topic} dla {subject}.",
        "Obserwacje w {context} potwierdzają znaczenie {topic}.",
    ),
)
```

- [ ] **Step 7: Zarejestruj motywy w `registry.py`**

```python
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.disney import DISNEY
from bpp.demo_data.themes.harry_potter import HARRY_POTTER
from bpp.demo_data.themes.lem import LEM
from bpp.demo_data.themes.realistyczny import REALISTYCZNY
from bpp.demo_data.themes.wiedzmin import WIEDZMIN

THEMES: dict[str, Theme] = {
    t.key: t for t in (REALISTYCZNY, LEM, WIEDZMIN, HARRY_POTTER, DISNEY)
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_themes.py -v`
Expected: PASS (w tym 4 parametryzowane)

- [ ] **Step 9: Commit**

```bash
git add src/bpp/demo_data/themes/ src/bpp/tests/test_demo_data/test_themes.py
git commit -m "feat(demo-data): motywy lem, wiedzmin, harry-potter, disney"
```

---

## Task 7: Generator streszczeń + `CLEANUP_ORDER`

**Files:**
- Create: `src/bpp/demo_data/generators/streszczenia.py`
- Modify: `src/bpp/demo_data/manifest.py` (CLEANUP_ORDER)
- Test: `src/bpp/tests/test_demo_data/test_generator_streszczenia.py`

- [ ] **Step 1: Write failing test**

Utwórz `src/bpp/tests/test_demo_data/test_generator_streszczenia.py`:

```python
"""Test generatora streszczeń (Wydawnictwo_*_Streszczenie)."""

import random

import pytest
from model_bakery import baker

from bpp.demo_data.generators.streszczenia import create_streszczenia
from bpp.demo_data.manifest import Manifest
from bpp.models import (
    Jezyk,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Streszczenie,
)
from bpp.demo_data.themes.registry import get_theme


@pytest.fixture
def prace(db):
    baker.make(Jezyk, nazwa="polski", skrot="pol.")
    wc = [baker.make(Wydawnictwo_Ciagle) for _ in range(4)]
    wz = [baker.make(Wydawnictwo_Zwarte) for _ in range(4)]
    return wc, wz


@pytest.mark.django_db(transaction=True)
def test_streszczenia_100_percent(prace, tmp_manifest_path):
    wc, wz = prace
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    create_streszczenia(
        prace_wc=wc, prace_wz=wz, theme=get_theme("wiedzmin"), procent=100,
        manifest=m, rng=random.Random(1), batch_size=10, disable_progress=True,
    )
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 4
    assert Wydawnictwo_Zwarte_Streszczenie.objects.count() == 4
    s = Wydawnictwo_Ciagle_Streszczenie.objects.first()
    assert s.streszczenie  # niepuste
    assert s.jezyk_streszczenia.nazwa == "polski"  # polski znaleziony
    assert m.objects_for("bpp.Wydawnictwo_Ciagle_Streszczenie")


@pytest.mark.django_db(transaction=True)
def test_streszczenia_0_percent(prace, tmp_manifest_path):
    wc, wz = prace
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    create_streszczenia(
        prace_wc=wc, prace_wz=wz, theme=get_theme("lem"), procent=0,
        manifest=m, rng=random.Random(1), batch_size=10, disable_progress=True,
    )
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 0
    assert Wydawnictwo_Zwarte_Streszczenie.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_streszczenia_jezyk_none_when_no_polski(tmp_manifest_path, db):
    # Brak Jezyka 'polski' → fallback None (pole nullable), bez crashu.
    wc = [baker.make(Wydawnictwo_Ciagle) for _ in range(2)]
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    create_streszczenia(
        prace_wc=wc, prace_wz=[], theme=get_theme("realistyczny"), procent=100,
        manifest=m, rng=random.Random(1), batch_size=10, disable_progress=True,
    )
    s = Wydawnictwo_Ciagle_Streszczenie.objects.first()
    assert s.jezyk_streszczenia is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_streszczenia.py -v`
Expected: FAIL — `ModuleNotFoundError: ...generators.streszczenia`

- [ ] **Step 3: Write `streszczenia.py`**

```python
"""Generator streszczeń (Wydawnictwo_Ciagle/Zwarte_Streszczenie)."""

from __future__ import annotations

import random
from collections.abc import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import compose_streszczenie
from bpp.models import (
    Jezyk,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Streszczenie,
)


def _jezyk_polski() -> Jezyk | None:
    """Kanoniczny lookup polskiego (jak bpp/models/patent.py:56), z fallback."""
    return Jezyk.objects.filter(nazwa__icontains="polski").first()


def _create_for(
    *, model, label, prace, theme, procent, jezyk, manifest, rng,
    batch_size, disable_progress,
):
    objs = [
        model(
            rekord=praca,
            streszczenie=compose_streszczenie(theme, rng),
            jezyk_streszczenia=jezyk,
        )
        for praca in prace
        if rng.randint(1, 100) <= procent
    ]
    if not objs:
        return
    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc=f"Streszczenia {label}",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar:
        chunk = objs[start : start + batch_size]
        model.objects.bulk_create(chunk)
        manifest.append(label, [o.pk for o in chunk])
        manifest.save()


def create_streszczenia(
    *,
    prace_wc: Iterable[Wydawnictwo_Ciagle],
    prace_wz: Iterable[Wydawnictwo_Zwarte],
    theme: Theme,
    procent: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> None:
    """Tworzy 1 streszczenie (PL) dla ~procent% prac WC i WZ."""
    if not 0 <= procent <= 100:
        raise ValueError(f"procent musi być w [0, 100], dostał {procent}")
    jezyk = _jezyk_polski()
    _create_for(
        model=Wydawnictwo_Ciagle_Streszczenie,
        label="bpp.Wydawnictwo_Ciagle_Streszczenie",
        prace=list(prace_wc), theme=theme, procent=procent, jezyk=jezyk,
        manifest=manifest, rng=rng, batch_size=batch_size,
        disable_progress=disable_progress,
    )
    _create_for(
        model=Wydawnictwo_Zwarte_Streszczenie,
        label="bpp.Wydawnictwo_Zwarte_Streszczenie",
        prace=list(prace_wz), theme=theme, procent=procent, jezyk=jezyk,
        manifest=manifest, rng=rng, batch_size=batch_size,
        disable_progress=disable_progress,
    )
```

- [ ] **Step 4: Dodaj wpisy do `CLEANUP_ORDER` w `manifest.py`**

Po `"bpp.Wydawnictwo_Zwarte_Autor",` a PRZED `"bpp.Wydawnictwo_Ciagle",`:

```python
    "bpp.Wydawnictwo_Ciagle_Autor",
    "bpp.Wydawnictwo_Zwarte_Autor",
    # Streszczenia (FK rekord → praca, CASCADE) — usuwamy przed rekordami:
    "bpp.Wydawnictwo_Ciagle_Streszczenie",
    "bpp.Wydawnictwo_Zwarte_Streszczenie",
    # Potem rekordy:
    "bpp.Wydawnictwo_Ciagle",
    "bpp.Wydawnictwo_Zwarte",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_streszczenia.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/bpp/demo_data/generators/streszczenia.py src/bpp/demo_data/manifest.py \
    src/bpp/tests/test_demo_data/test_generator_streszczenia.py
git commit -m "feat(demo-data): generator tematycznych streszczeń + CLEANUP_ORDER"
```

---

## Task 8: Orchestrator — wiring motywu, prefiksu, streszczeń, defaulty lat

**Files:**
- Modify: `src/bpp/demo_data/orchestrator.py`
- Test: pokryte przez `test_command_create.py` (Task 9)

- [ ] **Step 1: `CreateOptions` — nowe pola**

W `@dataclass CreateOptions` dodaj (po `confirm_db`, przed `disable_progress`):

```python
    motyw: str = "realistyczny"
    procent_ze_streszczeniem: int = 70
    bez_prefiksu: bool = False
```

- [ ] **Step 2: `run_create` — resolve theme + prefix, przekaż do generatorów**

Po inicjalizacji `rng` i `manifest` dodaj:

```python
    from bpp.demo_data.generators.streszczenia import create_streszczenia
    from bpp.demo_data.themes.registry import get_theme

    theme = get_theme(opts.motyw)
    prefix = "" if opts.bez_prefiksu else "Demo — "
```

Następnie do wywołań dołóż argumenty:
- `ensure_uczelnia(manifest, theme=theme, prefix=prefix)`
- `create_wydzialy(..., theme=theme, prefix=prefix)`
- `create_jednostki(..., theme=theme, prefix=prefix)`
- `create_autorzy(..., theme=theme)` (bez prefiksu — nazwiska czyste)
- `create_zrodla(..., theme=theme, prefix=prefix)`
- `create_wydawcy(..., theme=theme, prefix=prefix)`
- `wc = create_wc(..., theme=theme, prefix=prefix)` (przypisz wynik)
- `wz = create_wz(..., theme=theme, prefix=prefix)` (przypisz wynik)

Zmień przypisania:

```python
    wc = create_wc(
        n=opts.ile_ciaglych, autorzy=autorzy, zrodla=zrodla,
        lata=range(opts.od_roku, opts.do_roku + 1), theme=theme, prefix=prefix,
        manifest=manifest, rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    wz = create_wz(
        n=opts.ile_zwartych, autorzy=autorzy, wydawcy=wydawcy,
        lata=range(opts.od_roku, opts.do_roku + 1), theme=theme, prefix=prefix,
        manifest=manifest, rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    create_streszczenia(
        prace_wc=wc, prace_wz=wz, theme=theme,
        procent=opts.procent_ze_streszczeniem, manifest=manifest, rng=rng,
        batch_size=opts.batch_size, disable_progress=opts.disable_progress,
    )
```

- [ ] **Step 3: Banner — wzmianka o motywie i streszczeniach**

W końcowym `stdout.write(...)` dopisz na początku linię:

```python
        f"\n[OK] Motyw: {theme.label}. Streszczenia: ~{opts.procent_ze_streszczeniem}% prac.\n"
```

- [ ] **Step 4: Verify import**

Run: `uv run python -c "from bpp.demo_data.orchestrator import run_create, CreateOptions; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/bpp/demo_data/orchestrator.py
git commit -m "feat(demo-data): orchestrator — motyw, prefiks, streszczenia w pipeline"
```

---

## Task 9: Komenda — flagi `--motyw` / `--procent-ze-streszczeniem` / `--bez-prefiksu` + defaulty lat

**Files:**
- Modify: `src/bpp/management/commands/create_demo_data.py`
- Test: `src/bpp/tests/test_demo_data/test_command_create.py`

- [ ] **Step 1: Write failing test (dopisz do `test_command_create.py`)**

```python
@pytest.mark.django_db(transaction=True)
def test_command_with_theme_and_streszczenia(fixtures_loaded, tmp_path):
    """Motyw wiedzmin + streszczenia 100% + bez prefiksu."""
    from model_bakery import baker

    from bpp.models import Jezyk, Wydawnictwo_Ciagle_Streszczenie

    if not Jezyk.objects.filter(nazwa__icontains="polski").exists():
        baker.make(Jezyk, nazwa="polski", skrot="pol.")

    manifest = tmp_path / "m.json"
    call_command(
        "create_demo_data",
        "--motyw=wiedzmin",
        "--bez-prefiksu",
        "--procent-ze-streszczeniem=100",
        "--wydzialow=1", "--jednostek-na-wydzial=1", "--autorow=3",
        "--ile-ciaglych=3", "--ile-zwartych=3", "--zrodel=2", "--wydawcow=2",
        "--seed=1", f"--manifest-out={manifest}", "--batch-size=10",
        "--yes-i-am-sure", f"--confirm-db={connection.settings_dict['NAME']}",
    )
    # bez prefiksu: żadna jednostka nie zaczyna się od "Demo —"
    for j in Jednostka.objects.all():
        assert not j.nazwa.startswith("Demo —")
    # streszczenia powstały dla prac WC
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest "src/bpp/tests/test_demo_data/test_command_create.py::test_command_with_theme_and_streszczenia" -v`
Expected: FAIL — `error: unrecognized arguments: --motyw=wiedzmin`

- [ ] **Step 3: Dodaj flagi w `create_demo_data.py`**

W `add_arguments` dodaj (import na górze: `from bpp.demo_data.themes.registry import THEMES`):

```python
        parser.add_argument(
            "--motyw", type=str, default="realistyczny", choices=sorted(THEMES)
        )
        parser.add_argument("--procent-ze-streszczeniem", type=int, default=70)
        parser.add_argument("--bez-prefiksu", action="store_true")
```

Zmień defaulty lat:

```python
        parser.add_argument("--od-roku", type=int, default=2020)
        parser.add_argument("--do-roku", type=int, default=2026)
```

W budowie `CreateOptions(...)` w `handle` dodaj:

```python
            motyw=options["motyw"],
            procent_ze_streszczeniem=options["procent_ze_streszczeniem"],
            bez_prefiksu=options["bez_prefiksu"],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest "src/bpp/tests/test_demo_data/test_command_create.py::test_command_with_theme_and_streszczenia" -v`
Expected: PASS

- [ ] **Step 5: Run full command test file (regresja istniejących)**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_command_create.py -v`
Expected: PASS (wszystkie, w tym dotychczasowe smoke/preflight/abort)

- [ ] **Step 6: Commit**

```bash
git add src/bpp/management/commands/create_demo_data.py \
    src/bpp/tests/test_demo_data/test_command_create.py
git commit -m "feat(demo-data): flagi --motyw/--procent-ze-streszczeniem/--bez-prefiksu, lata 2020-2026"
```

---

## Task 10: Dokumentacja + roundtrip cleanup ze streszczeniami

**Files:**
- Create: `docs/demo-data.md` (krótki howto)
- Modify: `mkdocs.yml` (dodaj stronę do nav, jeśli istnieje sekcja)
- Test: `src/bpp/tests/test_demo_data/test_command_create.py` (roundtrip)

- [ ] **Step 1: Write roundtrip test (dopisz)**

```python
@pytest.mark.django_db(transaction=True)
def test_cleanup_removes_streszczenia(fixtures_loaded, tmp_path):
    from model_bakery import baker

    from bpp.models import Jezyk, Wydawnictwo_Ciagle_Streszczenie

    if not Jezyk.objects.filter(nazwa__icontains="polski").exists():
        baker.make(Jezyk, nazwa="polski", skrot="pol.")

    manifest = tmp_path / "m.json"
    call_command(
        "create_demo_data", "--motyw=lem", "--procent-ze-streszczeniem=100",
        "--wydzialow=1", "--jednostek-na-wydzial=1", "--autorow=3",
        "--ile-ciaglych=3", "--ile-zwartych=3", "--zrodel=2", "--wydawcow=2",
        "--seed=1", f"--manifest-out={manifest}", "--batch-size=10",
        "--yes-i-am-sure", f"--confirm-db={connection.settings_dict['NAME']}",
    )
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 3
    call_command(
        "cleanup_demo_data", f"--manifest={manifest}",
        "--yes-i-am-sure", f"--confirm-db={connection.settings_dict['NAME']}",
    )
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 0
    assert Wydawnictwo_Ciagle.objects.count() == 0
```

- [ ] **Step 2: Run test**

Run: `uv run pytest "src/bpp/tests/test_demo_data/test_command_create.py::test_cleanup_removes_streszczenia" -v`
Expected: PASS

- [ ] **Step 3: Napisz `docs/demo-data.md`**

```markdown
# Dane demo (`create_demo_data`)

Generator syntetycznych danych demo z wymiennymi motywami.

## Szybki start

\`\`\`bash
uv run python src/manage.py create_demo_data \
    --motyw wiedzmin \
    --autorow 200 --ile-ciaglych 1000 --ile-zwartych 500 \
    --yes-i-am-sure --confirm-db <NAZWA_BAZY>
\`\`\`

## Motywy (`--motyw`)

- `realistyczny` (domyślny) — polskie dane akademickie
- `lem` — Stanisław Lem
- `wiedzmin` — Wiedźmin
- `harry-potter` — Harry Potter
- `disney` — Disney

## Wybrane flagi

- `--bez-prefiksu` — pełny realizm (bez markera „Demo —")
- `--procent-ze-streszczeniem 70` — odsetek prac ze streszczeniem
- `--od-roku 2020 --do-roku 2026` — zakres lat prac
- `--seed 123` — deterministyczny wynik

## Sprzątanie

Manifest zapisany przy tworzeniu (np. `demo_data_manifest_*.json`):

\`\`\`bash
uv run python src/manage.py cleanup_demo_data \
    --manifest <plik.json> --yes-i-am-sure --confirm-db <NAZWA_BAZY>
\`\`\`

> Cleanup usuwa wyłącznie obiekty z manifestu (po PK) — bezpieczny dla
> istniejących danych. Po `create_demo_data` uruchom `denorm_flush`, by
> wypełnić cache opisów bibliograficznych.
```

> **UWAGA:** w pliku `.md` użyj prawdziwych potrójnych backticków zamiast
> `\`\`\``.

- [ ] **Step 4: Dodaj stronę do `mkdocs.yml` nav (jeśli sekcja istnieje)**

Run: `grep -n "nav:" mkdocs.yml | head -1`
Jeśli `nav:` istnieje, dodaj pod odpowiednią sekcją (np. administrator/developer): `      - Dane demo: demo-data.md`. Jeśli nie ma `nav:` — pomiń (MkDocs auto-wykryje plik).

- [ ] **Step 5: Commit**

```bash
git add docs/demo-data.md mkdocs.yml src/bpp/tests/test_demo_data/test_command_create.py
git commit -m "docs(demo-data): howto motywów + test cleanup streszczeń"
```

---

## Task 11: Domknięcie — lint, pełny przebieg testów

**Files:** (bez nowych)

- [ ] **Step 1: Ruff format + check**

Run: `cd ~/Programowanie/bpp-demo-themes && ruff format src/bpp/demo_data src/bpp/tests/test_demo_data && ruff check src/bpp/demo_data src/bpp/tests/test_demo_data`
Expected: brak błędów (jeśli `ruff check` zgłosi — popraw RĘCZNIE Editem, NIE `--fix`)

- [ ] **Step 2: Pełny przebieg testów demo_data**

Run: `uv run pytest src/bpp/tests/test_demo_data/ -v`
Expected: wszystkie PASS (themes, generatory, streszczenia, command, manifest, confirm, preflight, progress)

- [ ] **Step 3: Pre-commit na zmienionych plikach**

Run: `pre-commit run --files $(git diff --name-only origin/dev...HEAD)`
Expected: wszystkie hooki pass (lub poprawki RĘCZNE, potem ponów)

- [ ] **Step 4: (Opcjonalnie) Smoke przez run-site**

```bash
uv run run-site run --no-browser --no-celery &
# poczekaj na banner, potem w osobnym terminalu / przez dotfile:
PG_PORT=$(cat .dev_helpers_pg_port)
# create_demo_data --motyw wiedzmin ... na bazie run-site, obejrzyj nazwy
```

Cel: wzrokowa weryfikacja, że jednostki/źródła/wydawcy mają realistyczne
tematyczne nazwy (zero „Jednostka 1-1") i że streszczenia są widoczne w UI.

- [ ] **Step 5: Commit (jeśli ruff/pre-commit coś poprawiły)**

```bash
git add -A && git commit -m "chore(demo-data): lint + formatowanie" || echo "nic do commitu"
```

---

## Self-Review (wypełnione przez autora planu)

**1. Spec coverage:**
- System motywów (Theme/compose/registry) → Task 1–3, 6 ✓
- Realistyczne nazewnictwo (koniec „Jednostka 1-1") → Task 4 (jednostki/źródła/wydawcy) ✓
- Postacie→autorzy → Task 4 (autorzy compose_autor) ✓
- Tytuły z motywu + marker konfigurowalny → Task 5 ✓
- 5 motywów (realistyczny + 4) → Task 3, 6 ✓
- Streszczenia (model potomny + manifest + cleanup) → Task 7, 10 ✓
- Flagi --motyw/--procent-ze-streszczeniem/--bez-prefiksu + lata 2020-2026 → Task 9 ✓
- Bezpieczeństwo bez zmian (preflight/confirm/manifest-DB/cleanup po PK) → niezmieniane, regresja w Task 9/10 ✓
- Determinizm → testy compose (Task 2), istniejący test_seed_determinism (Task 4) ✓

**2. Placeholder scan:** Jedyne „...” są w Task 3 Step 3 z JAWNĄ instrukcją skopiowania pełnych krotek z `names.py` (dane istnieją w repo, nie wymyślamy). Brak innych TBD/TODO.

**3. Type/signature consistency:** Sygnatury keyword-only spójne: `theme: Theme` + `prefix: str=""` w generatorach encji; `theme` (bez prefiksu) w `create_autorzy`; `theme` + `prefix` w `create_wc/create_wz`; `make_tytul(theme, rng, idx, *, marker, rola)`; `create_streszczenia(prace_wc, prace_wz, theme, procent, ...)`. Klucze motywów: `realistyczny`, `lem`, `wiedzmin`, `harry-potter`, `disney` (z myślnikiem — spójne w registry, CLI choices i testach).
