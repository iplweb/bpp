# Import: słowniki stopień/stanowisko — Plan 2: import_common + parsery + mapowanie

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Czyste/testowalne jednostkowo warstwy dolne: klasyfikatory słowników (`stopien`, `stanowisko`, `jednostka_niepelna`), parser „komórki złożonej", split „nazwisko imię", oraz warstwa mapowania (cele, synonimy, reguła kontekstowa `stopień`, walidacja) + profil „ostatnio użyty".

**Architecture:** Klasyfikatory mirrorują `import_common/core/tytul.py` (porównanie po `normalize_*`, trigram ≥0.85). Parsery to czyste funkcje (bez ORM, poza `sklasyfikuj_jednostke_niepelna`, które czyta DB). Mapowanie rozszerza `import_pracownikow/mapping.py`; `zaproponuj_mapowanie` staje się świadome całego zbioru nagłówków. Profil to zmiana w `MapowanieForm`/`MapowanieView`.

**Tech Stack:** Django, PostgreSQL trigram (`pg_trgm`), pytest + `model_bakery`, pytest-testcontainers.

**Spec:** `docs/superpowers/specs/2026-07-12-import-slowniki-stopnie-stanowiska-design.md` (§5, §6, §7, §8, §9, §13)

**Zależność:** wymaga Planu 1 (modele `StopienSluzbowy`/`StanowiskoDydaktyczne` muszą istnieć).

## Global Constraints

- **ZAWSZE `uv run`** przed komendami Python. Max linia **88 znaków** (ruff).
- Testy: pytest, `@pytest.mark.django_db` gdzie DB, `baker.make`. Docker dla testcontainers (OrbStack: `export DOCKER_HOST=unix:///Users/mpasternak/.orbstack/run/docker.sock`).
- **Reguła kontekstowa `stopień`:** goły „stopień"/„stopien" → `stopień_służbowy` TYLKO gdy w zbiorze nagłówków jest też kolumna mapująca na `tytuł_stopień` (INNA niż sam goły stopień); inaczej → `tytuł_stopień`.
- **Nazewnictwo importu:** cel/klucz „stanowiska dydaktycznego" = `stanowisko_dydaktyczne` (kolizja z legacy `stanowisko`=funkcja). Cel „niepełnej nazwy" = `nazwa_jednostki_niepelna` (cel == klucz; `remapuj_wiersz` nie tłumaczy kluczy).
- **`funkcja` relabel:** KEY celu zostaje `stanowisko` — tylko etykieta „Funkcja w jednostce" + synonim `funkcja`.
- Branch: `feat/import-pracownikow-slowniki-stopnie-stanowiska`.

## File Structure (Plan 2)

- Create: `src/import_common/core/stopien.py` — klasyfikator stopni.
- Create: `src/import_common/core/stanowisko.py` — klasyfikator stanowisk.
- Modify: `src/import_common/core/jednostka.py` — `sklasyfikuj_jednostke_niepelna`.
- Create: `src/import_pracownikow/parsers/jednostka_zlozona.py` — parser komórki.
- Modify: `src/import_pracownikow/parsers/wartosci.py` — `rozbij_nazwisko_imie`.
- Modify: `src/import_pracownikow/mapping.py` — cele, synonimy, reguła kontekstowa, walidacja.
- Modify: `src/import_pracownikow/forms.py` — hidden field `profil_zastosowany`.
- Modify: `src/import_pracownikow/views.py` — fallback profilu + stempel `ostatnio_uzyty`.
- Testy: `src/import_common/tests/test_sklasyfikuj_stopien.py`, `test_sklasyfikuj_stanowisko.py`, `test_sklasyfikuj_jednostke_niepelna.py`; `src/import_pracownikow/tests/test_parser_komorki.py`, `test_parser_nazwisko_imie.py`, `test_mapping_nowe_cele.py`, `test_mapping_regula_stopien.py`, `test_profil_ostatnio_uzyty.py`.

---

## Task 1: Klasyfikator stopni służbowych (`import_common/core/stopien.py`)

**Files:**
- Test: `src/import_common/tests/test_sklasyfikuj_stopien.py` (create)
- Create: `src/import_common/core/stopien.py`

**Interfaces:**
- Consumes: `bpp.models.StopienSluzbowy` (Plan 1).
- Produces: `sklasyfikuj_stopien(s, *, prog=0.85) -> (StopienSluzbowy|None, status, sim|None)`; `normalize_stopien(s) -> str`; `zaproponuj_skrot_stopnia(s) -> str`; stałe `STATUS_STOPIEN_{TWARDY,ZGADYWANIE,BRAK}`.

- [ ] **Step 1: Write the failing test**

Create `src/import_common/tests/test_sklasyfikuj_stopien.py`:

```python
import pytest
from model_bakery import baker

from import_common.core.stopien import (
    STATUS_STOPIEN_BRAK,
    STATUS_STOPIEN_TWARDY,
    normalize_stopien,
    sklasyfikuj_stopien,
    zaproponuj_skrot_stopnia,
)


def test_normalize_usuwa_kropki_i_spacje():
    assert normalize_stopien("st. kpt.") == "st kpt"
    assert normalize_stopien("  Mł.  Bryg. ") == "mł bryg"
    assert normalize_stopien("") == ""
    assert normalize_stopien(None) == ""


def test_zaproponuj_skrot_przycina():
    assert zaproponuj_skrot_stopnia("kpt.") == "kpt."
    assert zaproponuj_skrot_stopnia(None) == ""


@pytest.mark.django_db
def test_pusty_stopien_to_brak():
    assert sklasyfikuj_stopien("") == (None, STATUS_STOPIEN_BRAK, None)
    assert sklasyfikuj_stopien(None) == (None, STATUS_STOPIEN_BRAK, None)


@pytest.mark.django_db
def test_dopasowanie_twarde_mimo_kropek():
    s = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    obj, status, sim = sklasyfikuj_stopien("KPT")
    assert obj == s
    assert status == STATUS_STOPIEN_TWARDY
    assert sim is None


@pytest.mark.django_db
def test_brak_dopasowania_to_brak():
    baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    obj, status, sim = sklasyfikuj_stopien("zupełnie inny xyz")
    assert obj is None
    assert status == STATUS_STOPIEN_BRAK
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_common/tests/test_sklasyfikuj_stopien.py -v`
Expected: FAIL — `ModuleNotFoundError: import_common.core.stopien`.

- [ ] **Step 3: Write implementation**

Create `src/import_common/core/stopien.py`:

```python
"""Klasyfikacja stopni służbowych z importu pracowników.

Mirror ``import_common/core/tytul.py`` — stopnie mają kropki (``st. kpt.``),
więc dopasowanie DOKŁADNE liczymy po ``normalize_stopien`` OBU stron (nie
SQL ``iexact``). Próg zgadywania jak dla tytułów (0.85 — krótkie stringi).
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from bpp.models import StopienSluzbowy

PROG_ZGADYWANIA_STOPNIA = 0.85

STATUS_STOPIEN_TWARDY = "twardy"
STATUS_STOPIEN_ZGADYWANIE = "zgadywanie"
STATUS_STOPIEN_BRAK = "brak"


def normalize_stopien(s):
    """Kanonikalizacja DO PORÓWNANIA: lower + strip + zwinięcie spacji +
    usunięcie kropek. ``None``/pusty → ``""``."""
    if not s:
        return ""
    return " ".join(s.lower().replace(".", "").split())


def sklasyfikuj_stopien(stopien_str, *, prog=PROG_ZGADYWANIA_STOPNIA):
    """Zwraca ``(StopienSluzbowy|None, status, similarity|None)`` bez rzucania."""
    if not stopien_str:
        return None, STATUS_STOPIEN_BRAK, None
    norm = normalize_stopien(stopien_str)
    if not norm:
        return None, STATUS_STOPIEN_BRAK, None

    for s in StopienSluzbowy.objects.all():
        if norm in (normalize_stopien(s.nazwa), normalize_stopien(s.skrot)):
            return s, STATUS_STOPIEN_TWARDY, None

    best = (
        StopienSluzbowy.objects.annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", norm),
                TrigramSimilarity("skrot", norm),
            )
        )
        .order_by("-sim")
        .first()
    )
    if best is not None and best.sim is not None and best.sim >= prog:
        return best, STATUS_STOPIEN_ZGADYWANIE, float(best.sim)
    return None, STATUS_STOPIEN_BRAK, None


def zaproponuj_skrot_stopnia(s):
    """Domyślny skrót nowego stopnia: forma źródłowa przycięta do 128."""
    return (s or "").strip()[:128]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_common/tests/test_sklasyfikuj_stopien.py -v`
Expected: PASS (5 testów).

- [ ] **Step 5: Commit**

```bash
git add src/import_common/core/stopien.py src/import_common/tests/test_sklasyfikuj_stopien.py
git commit -m "feat(import_common): klasyfikator stopni służbowych (mirror tytul)"
```

---

## Task 2: Klasyfikator stanowisk dydaktycznych (`import_common/core/stanowisko.py`)

**Files:**
- Test: `src/import_common/tests/test_sklasyfikuj_stanowisko.py` (create)
- Create: `src/import_common/core/stanowisko.py`

**Interfaces:**
- Consumes: `bpp.models.StanowiskoDydaktyczne` (Plan 1).
- Produces: `sklasyfikuj_stanowisko(s, *, prog=0.85) -> (StanowiskoDydaktyczne|None, status, sim|None)`; `normalize_stanowisko(s)`; `zaproponuj_skrot_stanowiska(s)`; stałe `STATUS_STANOWISKO_{TWARDY,ZGADYWANIE,BRAK}`.

- [ ] **Step 1: Write the failing test**

Create `src/import_common/tests/test_sklasyfikuj_stanowisko.py`:

```python
import pytest
from model_bakery import baker

from import_common.core.stanowisko import (
    STATUS_STANOWISKO_BRAK,
    STATUS_STANOWISKO_TWARDY,
    normalize_stanowisko,
    sklasyfikuj_stanowisko,
)


def test_normalize():
    assert normalize_stanowisko("Prof. Uczelni") == "prof uczelni"
    assert normalize_stanowisko(None) == ""


@pytest.mark.django_db
def test_pusty_to_brak():
    assert sklasyfikuj_stanowisko("") == (None, STATUS_STANOWISKO_BRAK, None)


@pytest.mark.django_db
def test_dopasowanie_twarde():
    s = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="adiunkt")
    obj, status, sim = sklasyfikuj_stanowisko("Adiunkt")
    assert obj == s
    assert status == STATUS_STANOWISKO_TWARDY


@pytest.mark.django_db
def test_brak_dopasowania():
    baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="adiunkt")
    obj, status, _ = sklasyfikuj_stanowisko("nieznane xyz")
    assert obj is None
    assert status == STATUS_STANOWISKO_BRAK
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_common/tests/test_sklasyfikuj_stanowisko.py -v`
Expected: FAIL — `ModuleNotFoundError: import_common.core.stanowisko`.

- [ ] **Step 3: Write implementation**

Create `src/import_common/core/stanowisko.py`:

```python
"""Klasyfikacja stanowisk dydaktycznych z importu pracowników.

Mirror ``import_common/core/stopien.py`` (identyczna mechanika, model
``StanowiskoDydaktyczne``). Porównanie po ``normalize_stanowisko``, trigram
≥0.85.
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from bpp.models import StanowiskoDydaktyczne

PROG_ZGADYWANIA_STANOWISKA = 0.85

STATUS_STANOWISKO_TWARDY = "twardy"
STATUS_STANOWISKO_ZGADYWANIE = "zgadywanie"
STATUS_STANOWISKO_BRAK = "brak"


def normalize_stanowisko(s):
    if not s:
        return ""
    return " ".join(s.lower().replace(".", "").split())


def sklasyfikuj_stanowisko(stanowisko_str, *, prog=PROG_ZGADYWANIA_STANOWISKA):
    if not stanowisko_str:
        return None, STATUS_STANOWISKO_BRAK, None
    norm = normalize_stanowisko(stanowisko_str)
    if not norm:
        return None, STATUS_STANOWISKO_BRAK, None

    for s in StanowiskoDydaktyczne.objects.all():
        if norm in (normalize_stanowisko(s.nazwa), normalize_stanowisko(s.skrot)):
            return s, STATUS_STANOWISKO_TWARDY, None

    best = (
        StanowiskoDydaktyczne.objects.annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", norm),
                TrigramSimilarity("skrot", norm),
            )
        )
        .order_by("-sim")
        .first()
    )
    if best is not None and best.sim is not None and best.sim >= prog:
        return best, STATUS_STANOWISKO_ZGADYWANIE, float(best.sim)
    return None, STATUS_STANOWISKO_BRAK, None


def zaproponuj_skrot_stanowiska(s):
    return (s or "").strip()[:128]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_common/tests/test_sklasyfikuj_stanowisko.py -v`
Expected: PASS (4 testy).

- [ ] **Step 5: Commit**

```bash
git add src/import_common/core/stanowisko.py src/import_common/tests/test_sklasyfikuj_stanowisko.py
git commit -m "feat(import_common): klasyfikator stanowisk dydaktycznych"
```

---

## Task 3: `sklasyfikuj_jednostke_niepelna` (fragment nazwy → jednostka)

**Files:**
- Test: `src/import_common/tests/test_sklasyfikuj_jednostke_niepelna.py` (create)
- Modify: `src/import_common/core/jednostka.py`

**Interfaces:**
- Consumes: istniejące `sklasyfikuj_jednostke`, `normalize_nazwa_jednostki`, `STATUS_JEDNOSTKA_*` (jednostka.py).
- Produces: `sklasyfikuj_jednostke_niepelna(fragment, wydzial=None, *, prog=PROG_ZGADYWANIA_JEDNOSTKI) -> (Jednostka|None, status, sim|None)`.

- [ ] **Step 1: Write the failing test**

Create `src/import_common/tests/test_sklasyfikuj_jednostke_niepelna.py`:

```python
import pytest
from model_bakery import baker

from import_common.core.jednostka import (
    STATUS_JEDNOSTKA_BRAK,
    STATUS_JEDNOSTKA_TWARDY,
    STATUS_JEDNOSTKA_ZGADYWANIE,
    sklasyfikuj_jednostke_niepelna,
)


@pytest.mark.django_db
def test_pusty_fragment_to_brak():
    assert sklasyfikuj_jednostke_niepelna("") == (None, STATUS_JEDNOSTKA_BRAK, None)


@pytest.mark.django_db
def test_dokladna_nazwa_to_twardy():
    j = baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    obj, status, _ = sklasyfikuj_jednostke_niepelna("Wydział Medyczny")
    assert obj == j
    assert status == STATUS_JEDNOSTKA_TWARDY


@pytest.mark.django_db
def test_fragment_trafia_przez_icontains_jako_zgadywanie():
    j = baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    obj, status, _ = sklasyfikuj_jednostke_niepelna("Medyczny")
    assert obj == j
    assert status == STATUS_JEDNOSTKA_ZGADYWANIE


@pytest.mark.django_db
def test_brak_trafienia():
    baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    obj, status, _ = sklasyfikuj_jednostke_niepelna("Kompletnie inny fragment zzz")
    assert obj is None
    assert status == STATUS_JEDNOSTKA_BRAK
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_common/tests/test_sklasyfikuj_jednostke_niepelna.py -v`
Expected: FAIL — `ImportError: cannot import name 'sklasyfikuj_jednostke_niepelna'`.

- [ ] **Step 3: Write implementation**

Dodaj na końcu `src/import_common/core/jednostka.py`:

```python
def sklasyfikuj_jednostke_niepelna(
    fragment, wydzial=None, *, prog=PROG_ZGADYWANIA_JEDNOSTKI
):
    """Klasyfikuje NIEPEŁNĄ nazwę jednostki (fragment, np. „Medyczny").

    Najpierw próba dokładna (``sklasyfikuj_jednostke``) — jeśli ``twardy``,
    zwróć. Inaczej ``nazwa__icontains`` w SZEROKIM zbiorze widocznych jednostek
    (CELOWO NIE ``_pula_afiliacyjna`` — wyklucza ona lustra wydziałów, przez co
    „Wydział Medyczny" nigdy by się nie znalazł). Wynik z gałęzi ``icontains``
    ma ZAWSZE status ``zgadywanie`` (fragment jest niejednoznaczny), nigdy
    ``twardy``. Ograniczenie: ``icontains`` nie łapie fleksji („Medyczny" ≠
    „Medycznego").
    """
    if not fragment:
        return None, STATUS_JEDNOSTKA_BRAK, None
    frag = normalize_nazwa_jednostki(fragment)
    if not frag:
        return None, STATUS_JEDNOSTKA_BRAK, None

    j, status, sim = sklasyfikuj_jednostke(fragment, wydzial)
    if status == STATUS_JEDNOSTKA_TWARDY:
        return j, status, sim

    best = (
        Jednostka.objects.filter(widoczna=True, nazwa__icontains=frag)
        .annotate(sim=TrigramSimilarity("nazwa", frag))
        .order_by("-sim")
        .first()
    )
    if best is not None:
        return (
            best,
            STATUS_JEDNOSTKA_ZGADYWANIE,
            float(best.sim) if best.sim is not None else None,
        )
    return None, STATUS_JEDNOSTKA_BRAK, None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_common/tests/test_sklasyfikuj_jednostke_niepelna.py -v`
Expected: PASS (4 testy).

- [ ] **Step 5: Commit**

```bash
git add src/import_common/core/jednostka.py src/import_common/tests/test_sklasyfikuj_jednostke_niepelna.py
git commit -m "feat(import_common): sklasyfikuj_jednostke_niepelna (icontains, poza pulą afiliacyjną)"
```

---

## Task 4: Parser „komórki złożonej" (`parsers/jednostka_zlozona.py`)

**Files:**
- Test: `src/import_pracownikow/tests/test_parser_komorki.py` (create)
- Create: `src/import_pracownikow/parsers/jednostka_zlozona.py`

**Interfaces:**
- Produces: `parsuj_komorke(komorka: str) -> dict` z kluczami `skrot: str|None`, `nazwa: str`, `oddzial: str|None`. Czysta funkcja (bez ORM).

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_parser_komorki.py`:

```python
import pytest

from import_pracownikow.parsers.jednostka_zlozona import parsuj_komorke


@pytest.mark.parametrize(
    "komorka,skrot,nazwa,oddzial",
    [
        (
            "RW-1/1 Zakład Kierowania Działaniami Ratowniczymi, Działań "
            "Gaśniczych i Łączności WIBiOL taktyka",
            "RW-1/1",
            "Zakład Kierowania Działaniami Ratowniczymi, Działań Gaśniczych "
            "i Łączności",
            "WIBiOL",
        ),
        # ogon za oddziałem zawiera wielkoliterowe „RM"
        (
            "RW-7/1 Zakład Medycznych Działań Ratowniczych WIBiOL medyczne RM",
            "RW-7/1",
            "Zakład Medycznych Działań Ratowniczych",
            "WIBiOL",
        ),
        # brak ogona
        (
            "RW-6/3 Zakład Nauk Społecznych WIBiOL",
            "RW-6/3",
            "Zakład Nauk Społecznych",
            "WIBiOL",
        ),
        # RN — brak oddziału, ogon lowercase „instytut ib"
        (
            "RN-1 Instytut Inżynierii Bezpieczeństwa instytut ib",
            "RN-1",
            "Instytut Inżynierii Bezpieczeństwa",
            None,
        ),
        # łączniki „i"/„w"/„Ppoż." w środku nazwy
        (
            "RW-2/2 Zakład Hydromechaniki i Ppoż. Zaopatrzenia w Wodę WIBiOL "
            "hydra hydromechanika",
            "RW-2/2",
            "Zakład Hydromechaniki i Ppoż. Zaopatrzenia w Wodę",
            "WIBiOL",
        ),
        # skrót bez ukośnika
        (
            "RW-9 Studium Wychowania Fizycznego WIBiOL wf",
            "RW-9",
            "Studium Wychowania Fizycznego",
            "WIBiOL",
        ),
        # pusta komórka
        ("", None, "", None),
    ],
)
def test_parsuj_komorke(komorka, skrot, nazwa, oddzial):
    wynik = parsuj_komorke(komorka)
    assert wynik["skrot"] == skrot
    assert wynik["nazwa"] == nazwa
    assert wynik["oddzial"] == oddzial
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_parser_komorki.py -v`
Expected: FAIL — `ModuleNotFoundError: import_pracownikow.parsers.jednostka_zlozona`.

- [ ] **Step 3: Write implementation**

Create `src/import_pracownikow/parsers/jednostka_zlozona.py`:

```python
"""Parser „komórki złożonej" APOŻ: ``RW-1/1 <Nazwa> WIBiOL <ogon>``.

Czysty rdzeń (bez ORM), testowalny tabelarycznie. Wynik zasila decyzję o
jednostce (skrót → ``skrot_hint`` reconcilera; nazwa → nazwa źródłowa; oddział
→ hint wydziału rozwiązywany PO skrócie w warstwie analizy).
"""

import re

# Skrót: RW-1/1, RN-2, RW-9 (litera(y) wielkie + myślnik + cyfry + opcjonalnie /cyfry).
_SKROT_RE = re.compile(r"^[A-ZŁŚŻĆŃÓ][A-ZŁŚŻĆŃÓ0-9]*-\d+(?:/\d+)?$")


def _jest_akronim(token):
    """Token „akronimowy" typu WIBiOL: len ≥3 i ≥2 wielkie litery."""
    wielkie = [c for c in token if c.isalpha() and c.isupper()]
    return len(token) >= 3 and len(wielkie) >= 2


def parsuj_komorke(komorka):
    """Zwraca ``{"skrot": str|None, "nazwa": str, "oddzial": str|None}``."""
    tokeny = (komorka or "").split()
    if not tokeny:
        return {"skrot": None, "nazwa": "", "oddzial": None}

    skrot = None
    start = 0
    if _SKROT_RE.match(tokeny[0]):
        skrot = tokeny[0]
        start = 1

    # Oddział = pierwszy token AKRONIMOWY PO skrócie (nie od tokenu 0 — sam
    # skrót „RW-1/1" też przechodzi heurystykę akronimu).
    oddzial = None
    oddzial_idx = None
    for i in range(start, len(tokeny)):
        if _jest_akronim(tokeny[i]):
            oddzial = tokeny[i]
            oddzial_idx = i
            break

    if oddzial_idx is not None:
        # Ogon = wszystko za oddziałem (bez patrzenia na wielkość liter).
        nazwa_tokeny = tokeny[start:oddzial_idx]
    else:
        # Brak oddziału → utnij KOŃCOWY ciąg tokenów all-lowercase (ogon-znacznik).
        nazwa_tokeny = tokeny[start:]
        while nazwa_tokeny and nazwa_tokeny[-1].islower():
            nazwa_tokeny.pop()

    return {"skrot": skrot, "nazwa": " ".join(nazwa_tokeny), "oddzial": oddzial}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_parser_komorki.py -v`
Expected: PASS (7 przypadków parametryzacji).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/parsers/jednostka_zlozona.py src/import_pracownikow/tests/test_parser_komorki.py
git commit -m "feat(import_pracownikow): parser komórki złożonej (skrót+nazwa+oddział)"
```

---

## Task 5: Split „nazwisko imię" (deterministyczny, nazwisko-first)

**Files:**
- Test: `src/import_pracownikow/tests/test_parser_nazwisko_imie.py` (create)
- Modify: `src/import_pracownikow/parsers/wartosci.py`

**Interfaces:**
- Produces: `rozbij_nazwisko_imie(dane: dict) -> dict` — mutuje `dane`, uzupełnia puste `nazwisko`/`imię` z klucza `nazwisko_imię`, usuwa klucz `nazwisko_imię`.

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_parser_nazwisko_imie.py`:

```python
from import_pracownikow.parsers.wartosci import rozbij_nazwisko_imie


def test_prosty_split():
    d = rozbij_nazwisko_imie({"nazwisko_imię": "Anszczak Marcin"})
    assert d["nazwisko"] == "Anszczak"
    assert d["imię"] == "Marcin"
    assert "nazwisko_imię" not in d


def test_nazwisko_z_lacznikiem():
    d = rozbij_nazwisko_imie({"nazwisko_imię": "Ciuka-Witrylak Małgorzata"})
    assert d["nazwisko"] == "Ciuka-Witrylak"
    assert d["imię"] == "Małgorzata"


def test_nie_nadpisuje_istniejacych():
    d = rozbij_nazwisko_imie(
        {"nazwisko_imię": "Anszczak Marcin", "nazwisko": "X", "imię": "Y"}
    )
    assert d["nazwisko"] == "X"
    assert d["imię"] == "Y"


def test_brak_klucza_no_op():
    d = rozbij_nazwisko_imie({"nazwisko": "Kowalski"})
    assert d == {"nazwisko": "Kowalski"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_parser_nazwisko_imie.py -v`
Expected: FAIL — `ImportError: cannot import name 'rozbij_nazwisko_imie'`.

- [ ] **Step 3: Write implementation**

Dodaj na końcu `src/import_pracownikow/parsers/wartosci.py`:

```python
def rozbij_nazwisko_imie(dane: dict) -> dict:
    """Deterministyczny split „Nazwisko Imię" (nazwisko-first): pierwszy token
    → ``nazwisko``, reszta → ``imię``. Uzupełnia tylko PUSTE pola. Mutuje i
    zwraca ``dane``; usuwa klucz ``nazwisko_imię`` (``AutorForm`` go nie zna).

    Ograniczenie: dwuczłonowe nazwiska bez łącznika nie są rozbijane (pierwszy
    token = całe nazwisko). ``Ciuka-Witrylak`` (łącznik = 1 token) działa.
    """
    combined = str(dane.get("nazwisko_imię") or "").strip()
    if combined:
        tokeny = combined.split()
        if tokeny:
            if not dane.get("nazwisko"):
                dane["nazwisko"] = tokeny[0]
            if not dane.get("imię"):
                dane["imię"] = " ".join(tokeny[1:])
    dane.pop("nazwisko_imię", None)
    return dane
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_parser_nazwisko_imie.py -v`
Expected: PASS (4 testy).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/parsers/wartosci.py src/import_pracownikow/tests/test_parser_nazwisko_imie.py
git commit -m "feat(import_pracownikow): deterministyczny split nazwisko-imię"
```

---

## Task 6: Mapowanie — nowe cele, synonimy, reguła kontekstowa, walidacja

**Files:**
- Test: `src/import_pracownikow/tests/test_mapping_nowe_cele.py` (create)
- Test: `src/import_pracownikow/tests/test_mapping_regula_stopien.py` (create)
- Modify: `src/import_pracownikow/mapping.py`

**Interfaces:**
- Consumes: istniejące `POLA_DOCELOWE`, `_SYNONIMY`, `POLE_POMIN`, `_dopasuj_naglowek`, `zaproponuj_mapowanie`, `waliduj_mapowanie`.
- Produces: nowe cele w `POLA_DOCELOWE` (`email`, `stopień_służbowy`, `stanowisko_dydaktyczne`, `nazwisko_imię`, `komórka_złożona`, `nazwa_jednostki_niepelna`); relabel celu `stanowisko` → „Funkcja w jednostce"; `zaproponuj_mapowanie` świadome zbioru nagłówków (reguła `stopień`); `waliduj_mapowanie` uznaje `nazwisko_imię` (identyfikacja) oraz `nazwa_jednostki_niepelna`/`komórka_złożona` (jednostka).

- [ ] **Step 1: Write the failing tests**

Create `src/import_pracownikow/tests/test_mapping_nowe_cele.py`:

```python
from import_pracownikow.mapping import (
    POLA_DOCELOWE,
    POLE_POMIN,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)


def _cele():
    return {k for k, _ in POLA_DOCELOWE}


def test_nowe_cele_obecne():
    for cel in [
        "email",
        "stopień_służbowy",
        "stanowisko_dydaktyczne",
        "nazwisko_imię",
        "komórka_złożona",
        "nazwa_jednostki_niepelna",
    ]:
        assert cel in _cele()


def test_synonimy_prostych_celow():
    m = zaproponuj_mapowanie(["email", "funkcja", "stanowisko_dydakt", "komórka"])
    assert m["email"] == "email"
    assert m["funkcja"] == "stanowisko"  # KEY funkcji zostaje „stanowisko"
    assert m["stanowisko_dydakt"] == "stanowisko_dydaktyczne"
    assert m["komórka"] == "komórka_złożona"


def test_nazwisko_imie_identyfikuje_osobe():
    # nazwisko_imię + komórka_złożona wystarcza (osoba + jednostka)
    assert waliduj_mapowanie(
        {"a": "nazwisko_imię", "b": "komórka_złożona"}
    ) == []


def test_niepelna_nazwa_spelnia_wymog_jednostki():
    assert waliduj_mapowanie(
        {"a": "nazwisko", "b": "imię", "c": "nazwa_jednostki_niepelna"}
    ) == []


def test_brak_jednostki_daje_blad():
    bledy = waliduj_mapowanie({"a": "nazwisko", "b": "imię"})
    assert any("jednostka" in e.lower() for e in bledy)
```

Create `src/import_pracownikow/tests/test_mapping_regula_stopien.py`:

```python
from import_pracownikow.mapping import zaproponuj_mapowanie


def test_stopien_z_tytulem_to_sluzbowy():
    m = zaproponuj_mapowanie(["tytuł", "stopień"])
    assert m["tytuł"] == "tytuł_stopień"
    assert m["stopień"] == "stopień_służbowy"


def test_sam_stopien_to_tytul_naukowy():
    m = zaproponuj_mapowanie(["stopień"])
    assert m["stopień"] == "tytuł_stopień"


def test_jawny_synonim_sluzbowy_bez_wzgledu_na_tytul():
    m = zaproponuj_mapowanie(["stopień_służbowy"])
    assert m["stopień_służbowy"] == "stopień_służbowy"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping_nowe_cele.py src/import_pracownikow/tests/test_mapping_regula_stopien.py -v`
Expected: FAIL (nowe cele/synonimy/reguła nie istnieją).

- [ ] **Step 3: Dodaj cele do `POLA_DOCELOWE`**

W `src/import_pracownikow/mapping.py`, w liście `POLA_DOCELOWE`: zmień etykietę wpisu `("stanowisko", "Stanowisko")` na `("stanowisko", "Funkcja w jednostce")`, oraz dodaj nowe wpisy (np. po `("orcid", "ORCID")` / w logicznych miejscach):

```python
    ("email", "E-mail"),
    ("stopień_służbowy", "Stopień służbowy"),
    ("stanowisko_dydaktyczne", "Stanowisko dydaktyczne"),
    ("nazwisko_imię", "Nazwisko i imię (jedna komórka, nazwisko-first)"),
    ("komórka_złożona", "Komórka (skrót + nazwa + oddział + znacznik)"),
    ("nazwa_jednostki_niepelna", "Niepełna nazwa jednostki"),
```

- [ ] **Step 4: Dodaj synonimy do `_SYNONIMY`**

W `_SYNONIMY` dodaj (NIE dodawaj gołego `stopień`/`stopien` — obsługuje je reguła kontekstowa w Step 6):

```python
    "email": "email",
    "e_mail": "email",
    "mail": "email",
    "poczta": "email",
    "adres_email": "email",
    "stopień_służbowy": "stopień_służbowy",
    "stopien_sluzbowy": "stopień_służbowy",
    "stopień_pożarniczy": "stopień_służbowy",
    "stopien_pozarniczy": "stopień_służbowy",
    "stanowisko_dydakt": "stanowisko_dydaktyczne",
    "stanowisko_dydaktyczne": "stanowisko_dydaktyczne",
    "stanowisko_dyd": "stanowisko_dydaktyczne",
    "funkcja": "stanowisko",
    "funkcja_w_jednostce": "stanowisko",
    "nazwisko_imię": "nazwisko_imię",
    "nazwisko_imie": "nazwisko_imię",
    "komórka": "komórka_złożona",
    "komorka": "komórka_złożona",
    "komorka_zlozona": "komórka_złożona",
```

- [ ] **Step 5: Rozszerz `waliduj_mapowanie` (identyfikacja + jednostka)**

W `waliduj_mapowanie`, w regule identyfikacji osoby dodaj `nazwisko_imię` jako trzecią alternatywę, a w regule jednostki dodaj `nazwa_jednostki_niepelna` i `komórka_złożona`:

```python
    ma_nazwisko_imie = _POLA_IDENTYFIKACJI <= set(uzyte)
    ma_osobe = "osoba_sklejona" in uzyte
    ma_nazwisko_imie_kol = "nazwisko_imię" in uzyte
    if not (ma_nazwisko_imie or ma_osobe or ma_nazwisko_imie_kol):
        bledy.append(
            "Brak identyfikacji osoby: zmapuj 'nazwisko' + 'imię', "
            "'osoba (sklejona)' albo 'nazwisko i imię (jedna komórka)'."
        )
    pola_jednostki = {"nazwa_jednostki", "nazwa_jednostki_niepelna", "komórka_złożona"}
    if not (pola_jednostki & set(uzyte)):
        bledy.append("Brak wymaganego pola: nazwa jednostki")
```

(Zastąp dotychczasowe dwa warunki — `ma_nazwisko_imie or ma_osobe` oraz `_POLE_JEDNOSTKA not in uzyte` — powyższymi.)

- [ ] **Step 6: Reguła kontekstowa `stopień` w `zaproponuj_mapowanie`**

Zastąp obecną implementację `zaproponuj_mapowanie` wersją świadomą zbioru nagłówków:

```python
# Nagłówki (znormalizowane) traktowane jako „goły stopień" — rozstrzygane
# kontekstowo (patrz zaproponuj_mapowanie).
_GOLY_STOPIEN = {"stopień", "stopien"}


def zaproponuj_mapowanie(naglowki):
    """``{naglowek: pole_docelowe}`` na podstawie synonimów + reguła kontekstowa.

    Goły „stopień"/„stopien" jest DWUZNACZNY: gdy w pliku jest TAKŻE kolumna
    tytułu (inny nagłówek → ``tytuł_stopień``), goły stopień oznacza stopień
    SŁUŻBOWY; gdy nie ma tytułu — stopień NAUKOWY (``tytuł_stopień``). Inaczej
    dwie kolumny wpadłyby oba na ``tytuł_stopień`` → duplikat celu → walidacja
    odrzuca plik.
    """
    baza = {h: _dopasuj_naglowek(h) for h in naglowki}
    # Czy istnieje kolumna tytułu INNA niż sam goły stopień?
    ma_tytul = any(
        cel == "tytuł_stopień" and h not in _GOLY_STOPIEN
        for h, cel in baza.items()
    )
    for h in naglowki:
        if h in _GOLY_STOPIEN:
            baza[h] = "stopień_służbowy" if ma_tytul else "tytuł_stopień"
    return baza
```

Uwaga: goły `stopień`/`stopien` NIE jest w `_SYNONIMY` (Step 4), więc `_dopasuj_naglowek` skieruje go fallbackiem `_SYNONIMY_ZAWIERA` na `tytuł_stopień` — a powyższy post-pass koryguje na `stopień_służbowy`, gdy jest tytuł.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping_nowe_cele.py src/import_pracownikow/tests/test_mapping_regula_stopien.py src/import_pracownikow/tests/test_mapping_ihit.py -v`
Expected: PASS (nowe testy + istniejący `test_mapping_ihit.py` bez regresji).

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/mapping.py \
  src/import_pracownikow/tests/test_mapping_nowe_cele.py \
  src/import_pracownikow/tests/test_mapping_regula_stopien.py
git commit -m "feat(import_pracownikow): nowe cele mapowania + reguła kontekstowa stopień + walidacja"
```

---

## Task 7: Profil „ostatnio użyty" (stempel przy zastosowaniu + fallback z progiem)

**Files:**
- Test: `src/import_pracownikow/tests/test_profil_ostatnio_uzyty.py` (create)
- Modify: `src/import_pracownikow/forms.py`
- Modify: `src/import_pracownikow/views.py`

**Interfaces:**
- Consumes: `ProfilMapowania` (istniejący, pola `mapowanie`, `ostatnio_uzyty`), `dopasuj_profil`, `MapowanieView`.
- Produces: ukryte pole `MapowanieForm.profil_zastosowany` (IntegerField); helper `wybierz_profil_fallback(naglowki, prog=0.5) -> ProfilMapowania|None` w `mapping.py`; stempel `ostatnio_uzyty` w `MapowanieView.form_valid`.

- [ ] **Step 1: Write the failing test**

Create `src/import_pracownikow/tests/test_profil_ostatnio_uzyty.py`:

```python
import pytest
from model_bakery import baker

from import_pracownikow.mapping import wybierz_profil_fallback


@pytest.mark.django_db
def test_fallback_zwraca_ostatnio_uzyty_gdy_pokrycie_wystarcza():
    baker.make(
        "import_pracownikow.ProfilMapowania",
        nazwa="stary",
        mapowanie={"nazwisko": "nazwisko", "imię": "imię"},
        ostatnio_uzyty="2026-01-01T00:00:00Z",
    )
    nowy = baker.make(
        "import_pracownikow.ProfilMapowania",
        nazwa="nowy",
        mapowanie={"nazwisko": "nazwisko", "imię": "imię"},
        ostatnio_uzyty="2026-07-01T00:00:00Z",
    )
    # nagłówki pliku pokrywają klucze profilu w 100% → powyżej progu 0.5
    assert wybierz_profil_fallback(["nazwisko", "imię"]) == nowy


@pytest.mark.django_db
def test_fallback_none_gdy_pokrycie_za_male():
    baker.make(
        "import_pracownikow.ProfilMapowania",
        nazwa="p",
        mapowanie={"a": "nazwisko", "b": "imię", "c": "email", "d": "orcid"},
        ostatnio_uzyty="2026-07-01T00:00:00Z",
    )
    # tylko 1 z 4 kluczy profilu obecny w nagłówkach → 0.25 < 0.5
    assert wybierz_profil_fallback(["a", "zzz"]) is None


@pytest.mark.django_db
def test_fallback_none_gdy_brak_profili():
    assert wybierz_profil_fallback(["nazwisko"]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_profil_ostatnio_uzyty.py -v`
Expected: FAIL — `ImportError: cannot import name 'wybierz_profil_fallback'`.

- [ ] **Step 3: Dodaj `wybierz_profil_fallback` w `mapping.py`**

Dodaj na końcu `src/import_pracownikow/mapping.py`:

```python
def wybierz_profil_fallback(naglowki, prog=0.5):
    """Ostatnio użyty profil jako fallback — TYLKO gdy pokrywa ≥ ``prog`` swoich
    kluczy w nagłówkach pliku. Chroni przed nałożeniem profilu z innej uczelni
    (np. reguła kontekstowa `stopień` §9 zostałaby zignorowana). Import lokalny
    (ORM lazy). Zwraca ``ProfilMapowania`` albo ``None``."""
    from import_pracownikow.models import ProfilMapowania

    zbior = set(naglowki)
    if not zbior:
        return None
    for profil in ProfilMapowania.objects.filter(
        ostatnio_uzyty__isnull=False
    ).order_by("-ostatnio_uzyty"):
        klucze = set(profil.mapowanie.keys())
        if not klucze:
            continue
        pokrycie = len(zbior & klucze) / len(klucze)
        if pokrycie >= prog:
            return profil
    return None
```

- [ ] **Step 4: Dodaj ukryte pole do `MapowanieForm`**

W `src/import_pracownikow/forms.py`, w klasie `MapowanieForm`, dodaj pole (obok `zapisz_profil`):

```python
    profil_zastosowany = forms.IntegerField(required=False, widget=forms.HiddenInput())
```

- [ ] **Step 5: Wpięcie fallbacku + stempla w `MapowanieView`**

W `src/import_pracownikow/views.py`, w `MapowanieView.get_form_kwargs`, po `dopasuj_profil` dodaj fallback i przekaż pk zastosowanego profilu jako initial ukrytego pola:

```python
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["naglowki"] = self._naglowki
        profil = dopasuj_profil(self._naglowki) or wybierz_profil_fallback(
            self._naglowki
        )
        if profil is not None:
            kwargs["initial_mapowanie"] = profil.mapowanie
            initial = kwargs.get("initial") or {}
            initial["profil_zastosowany"] = profil.pk
            kwargs["initial"] = initial
        return kwargs
```

Dodaj import na górze `views.py`: `from import_pracownikow.mapping import wybierz_profil_fallback` (obok istniejącego importu `dopasuj_profil`).

W `MapowanieView.form_valid`, PO bloku `if form.cleaned_data.get("zapisz_profil"):`, dodaj stempel zastosowanego profilu:

```python
        profil_pk = form.cleaned_data.get("profil_zastosowany")
        if profil_pk:
            ProfilMapowania.objects.filter(pk=profil_pk).update(
                ostatnio_uzyty=timezone.now()
            )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_profil_ostatnio_uzyty.py src/import_pracownikow/tests/test_views_mapowanie.py -v`
Expected: PASS (nowe testy + istniejące testy mapowania bez regresji).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/mapping.py src/import_pracownikow/forms.py \
  src/import_pracownikow/views.py \
  src/import_pracownikow/tests/test_profil_ostatnio_uzyty.py
git commit -m "feat(import_pracownikow): profil ostatnio użyty (fallback z progiem + stempel)"
```

---

## Weryfikacja końcowa Planu 2

- [ ] **Step 1: Uruchom testy Planu 2**

Run:
```bash
uv run pytest src/import_common/tests/test_sklasyfikuj_stopien.py \
  src/import_common/tests/test_sklasyfikuj_stanowisko.py \
  src/import_common/tests/test_sklasyfikuj_jednostke_niepelna.py \
  src/import_pracownikow/tests/test_parser_komorki.py \
  src/import_pracownikow/tests/test_parser_nazwisko_imie.py \
  src/import_pracownikow/tests/test_mapping_nowe_cele.py \
  src/import_pracownikow/tests/test_mapping_regula_stopien.py \
  src/import_pracownikow/tests/test_profil_ostatnio_uzyty.py \
  -v 2>&1 | tee /tmp/plan2_tests.log
```
Expected: wszystkie PASS.

- [ ] **Step 2: ruff**

Run: `ruff check src/import_common/core/stopien.py src/import_common/core/stanowisko.py src/import_common/core/jednostka.py src/import_pracownikow/parsers/jednostka_zlozona.py src/import_pracownikow/parsers/wartosci.py src/import_pracownikow/mapping.py src/import_pracownikow/forms.py src/import_pracownikow/views.py`
Expected: brak błędów.

**Deliverable Planu 2:** testowalne jednostkowo klasyfikatory (stopień/stanowisko/niepełna jednostka), parser komórki, split nazwisko-imię, kompletna warstwa mapowania (cele/synonimy/reguła kontekstowa/walidacja) i profil „ostatnio użyty". Nic jeszcze nie jest wpięte w analyze/integrate — to Plan 3.
