# Employment-change visibility + no-match resolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface three employment-change fields (wymiar etatu, grupa pracownicza, podstawowe miejsce pracy) in the import comparison grid, replace the buried no-match link+checkbox with an explicit Match/Create/Skip radio group, and add a non-blocking finalize warning when unresolved no-match rows would be silently skipped.

**Architecture:** Three independent, additive slices over the existing `import_pracownikow` preview pipeline. Section 1 extends the pure-read `porownaj_z_baza()` comparison dict with three new `{plik, baza, rozne}` triples rendered by the existing `_porownanie_kom.html`. Section 2 restyles the `brak`-row controls into one radio group, reusing the existing `PrzelaczUtworzNowegoView` (bool `utworz_nowego`) and `DopasujAutoraView` (Select2 pick) with no new model field. Section 3 adds a parent-model count + a warning partial + a `confirm()` on the finalize button.

**Tech Stack:** Django 5.2, pytest + model_bakery, HTMX 1.9.12, Foundation CSS (public frontend — monochrome `fi-*` Foundation-Icons, NOT emoji), Select2.

## Review corrections (Fable 5 review, 2026-07-14 — authoritative over conflicting task text below)

- **C1 (HTMX trigger scoping):** Do NOT use `hx-trigger="change from:.js-brak-radio-post"` — in htmx 1.9.12 a bare selector in `from:` binds document-wide, so one radio click fires **every** brak row's POST. Instead keep the three radios in one form with an **event filter**: `hx-trigger="change[target.classList.contains('js-brak-radio-post')]"`. The "Dopasuj" radio omits that class → it never fires the `utworz-nowego` POST (only the JS reveal). Single form preserves radio-group exclusivity (grouping is per form owner).
- **C2 / M5 (test markers & line length):** Every `_porownaj_fk_obj` test uses `baker.make(...)` → MUST carry `@pytest.mark.django_db`. `_porownaj_bool` tests are DB-free (no marker needed). Keep every test line ≤88 chars.
- **I1 (pluralize):** Django `pluralize` supports ≤2 forms and cannot express Polish declension. Use grammatically-invariant copy, NO `pluralize`: warning `Wiersze bez dopasowania zostaną pominięte przy zapisie: {{ liczba_pominietych }}.` and confirm `Wiersze bez dopasowania zostaną pominięte: N. Kontynuować zapis?`. Tests assert those exact stable substrings.
- **I2 (predicate scope — deliberate):** `liczba_wierszy_do_pominiecia()` = `autor__isnull=True, utworz_nowego=False` counts exactly the **"no decision made"** rows (design intent: user indecision). Rows with `utworz_nowego=True` but a deferred `jednostka` are gated by the separate jednostka-resolution flow upstream — NOT re-counted here. Document this in the method docstring.
- **I3 (N+1):** Base-side `aj.wymiar_etatu` / `aj.grupa_pracownicza` are NOT prefetched today (`get_details_set()` only select_relates `autor_jednostka__stanowisko` / `__funkcja`). Task 3 MUST add `"autor_jednostka__wymiar_etatu", "autor_jednostka__grupa_pracownicza"` to that `select_related` list. (`podstawowe_miejsce_pracy` is a local column — fine.)
- **I4 (real test scaffolding):** There is no `client_zalogowany` / `wiersz_brak` fixture. Use pytest-django's `admin_client, admin_user` and the existing helpers: `_wiersz(owner, confidence, stan)→(imp,row)` (`test_views_utworz_nowego.py:9`), `_imp/_url/_row` (`test_przeglad.py:23-38`). Preview grid renders via `reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk})`.
- **M4 (query dedup):** In `przeglad.html` wrap the warning block in `{% with liczba_pominietych=parent_object.liczba_wierszy_do_pominiecia %}` so the COUNT runs once, not three times.
- **M1 (backward-compat):** Existing `test_views_utworz_nowego.py` tests (`{"utworz_nowego": "on"}` / `{}`) keep passing with the `wybor`-first/legacy-fallback view logic — do NOT edit them.

## Global Constraints

- Max line length: 88 characters (ruff-enforced).
- NEVER modify existing migration files in `src/*/migrations/`. This plan adds **no** model fields → **no** migration.
- All Python commands run via `uv run` (e.g. `uv run pytest ...`).
- Public-frontend icons: monochrome Foundation-Icons `<span class="fi-*"></span>` / `<i class="fi-*"></i>`. NO emoji (emoji is admin-only).
- Django template comments `{# … #}` MUST be single-line — every line its own `{# … #}`.
- Tests: pytest style only (standalone functions, no `unittest.TestCase`), `@pytest.mark.django_db`, `model_bakery.baker.make` for DB objects.
- Add a towncrier newsfragment under `src/bpp/newsfragments/` (`<slug>.feature.rst`, Polish, one paragraph) — canonical dir, NOT `changes/newsfragments/`.
- Display-only fields (Section 1) are NOT wired into `POLA_ROZNIC` / the "pokaż tylko zmienione" field-state filter — mirroring how `data_od`/`data_do` already behave. No snapshot/`stany_pol` changes.

## Reference: existing code touchpoints (verified 2026-07-14)

- `src/import_pracownikow/models.py`
  - `ImportPracownikowRow.porownaj_z_baza()` — line 850. Pure read, returns
    `{email, stopien, stanowisko, tytul, funkcja, data_od, data_do}`.
  - `_porownaj_fk(plik_str, baza_obj, plik_id)` staticmethod — line 756. `rozne = plik_id is not None and baza_id != plik_id`.
  - `_porownaj_email` — line 742. `_porownaj_data` — line 771.
  - Row FK fields: `podstawowe_miejsce_pracy` (nullable bool, line 628), `grupa_pracownicza` (FK, 632), `wymiar_etatu` (FK, 635), `autor_jednostka` (FK, 624).
  - Parent props `ma_kolumne_stopnia` (line 524) / `ma_kolumne_stanowiska` (534) — both check `"<target>" in (self.mapowanie_kolumn or {}).values()`.
  - Parent counting example `liczniki_ludzi_z_xls()` — line 459.
  - `_wiersze_preview` `select_related` list — line 387 (already prefetches `grupa_pracownicza`, `funkcja_autora`, `wymiar_etatu`, `autor_jednostka__*`).
- `src/bpp/models/autor.py` — `Autor_Jednostka.podstawowe_miejsce_pracy` (nullable bool, 664), `grupa_pracownicza` (FK, 666), `wymiar_etatu` (FK, 669).
- `src/import_pracownikow/mapping.py` — targets: `grupa_pracownicza` (line 109), `wymiar_etatu_tekst` (111) / `wymiar_etatu_ulamek` (112), `podstawowe_miejsce_pracy` (120).
- Templates (`src/import_pracownikow/templates/import_pracownikow/`):
  - `partials/_porownanie_kom.html` — renders one `{plik, baza, rozne}` triple.
  - `partials/_wiersz_preview_kom.html` — comparison items at lines 213-253; `brak`-row controls at lines 70-102.
  - `partials/_ostrzezenie_podstawowe_miejsce.html` — the warning-partial pattern to mirror.
  - `przeglad.html` — finalize button at line 200; warning-include point at 190.
- Views (`src/import_pracownikow/views.py`):
  - `PrzelaczUtworzNowegoView` — line 465 (reads `request.POST.get("utworz_nowego") is not None`; guards `confidence != STATUS_BRAK`).
  - `DopasujAutoraView` — line 443 (binds `row.autor` via `_zwiaz_autora_z_wierszem`, transitions out of `brak`).
- `src/import_pracownikow/pewnosc.py` — `STATUS_BRAK = "brak"` (line 16).
- URL names: `import_pracownikow:utworz-nowego`, `:dopasuj-autora`, `:zatwierdz`.
- Existing tests to extend/mirror: `tests/test_porownywarka.py`, `tests/test_views_utworz_nowego.py`, `tests/test_views_preview_render.py`, `tests/test_przeglad.py`.

---

## File Structure

**Modify:**
- `src/import_pracownikow/models.py` — add 2 staticmethod comparators, 3 `ma_kolumne_*` props, extend `porownaj_z_baza()`, add 1 finalize-count method.
- `src/import_pracownikow/views.py` — tiny tweak to `PrzelaczUtworzNowegoView.post` (read radio value robustly).
- `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html` — add 3 comparison items; replace `brak` controls (70-102) with radio group.
- `src/import_pracownikow/templates/import_pracownikow/przeglad.html` — include new warning partial + `confirm()` on finalize button.

**Create:**
- `src/import_pracownikow/templates/import_pracownikow/partials/_ostrzezenie_brak_dopasowania.html` — finalize warning.
- `src/bpp/newsfragments/import-widocznosc-zatrudnienia.feature.rst` — newsfragment.
- Tests appended to existing files (no new test module required, but a new `tests/test_porownywarka_zatrudnienie.py` keeps the comparator suite focused).

---

## Task 1: Comparators `_porownaj_fk_obj` and `_porownaj_bool`

**Files:**
- Modify: `src/import_pracownikow/models.py` (next to `_porownaj_fk`, line 756)
- Test: `src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py` (new)

**Interfaces:**
- Produces:
  - `ImportPracownikowRow._porownaj_fk_obj(plik_obj, baza_obj, *, ma_baze=True) -> {"plik": str, "baza": str, "rozne": bool}` — staticmethod. Compares two FK **objects** by pk. `rozne = ma_baze and plik_obj is not None and (baza_obj is None or baza_obj.pk != plik_obj.pk)`.
  - `ImportPracownikowRow._porownaj_bool(plik_bool, baza_bool, *, ma_baze=True) -> {"plik": str, "baza": str, "rozne": bool}` — staticmethod. `plik`/`baza` render as `"Tak"`/`"Nie"`/`""` for `True`/`False`/`None`. `rozne = ma_baze and plik_bool is not None and plik_bool != baza_bool`.
- Consumes: nothing (pure staticmethods).

Rationale for the shape: `_porownanie_kom.html` already consumes `{plik, baza, rozne}` — matching that exactly means the template highlights (yellow "różne" label + grey "obecnie: …") for free. `ma_baze` mirrors `_porownaj_data`'s `ma_okres`: an unmatched row (no `autor_jednostka`) has no base to compare, so `ma_baze=False` forces `rozne=False` (show the file value plainly, no false highlight). Empty `plik` → `_porownanie_kom.html` renders `—`.

- [ ] **Step 1: Write the failing tests**

```python
# src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py
import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikowRow


def test_porownaj_fk_obj_zgodne_gdy_te_same_pk():
    obj = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(obj, obj)
    assert wynik["rozne"] is False
    assert wynik["plik"] == str(obj)
    assert wynik["baza"] == str(obj)


def test_porownaj_fk_obj_rozne_gdy_inne_pk():
    plik = baker.make("bpp.Wymiar_Etatu")
    baza = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(plik, baza)
    assert wynik["rozne"] is True
    assert wynik["plik"] == str(plik)
    assert wynik["baza"] == str(baza)


def test_porownaj_fk_obj_rozne_gdy_baza_pusta_a_plik_wskazuje():
    plik = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(plik, None)
    assert wynik["rozne"] is True
    assert wynik["baza"] == ""


def test_porownaj_fk_obj_niepodswietla_gdy_plik_pusty():
    baza = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(None, baza)
    assert wynik["rozne"] is False
    assert wynik["plik"] == ""


def test_porownaj_fk_obj_niepodswietla_gdy_brak_bazy_kontekstu():
    plik = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(plik, None, ma_baze=False)
    assert wynik["rozne"] is False


def test_porownaj_bool_tak_nie_pusto():
    assert ImportPracownikowRow._porownaj_bool(True, True)["plik"] == "Tak"
    assert ImportPracownikowRow._porownaj_bool(False, False)["plik"] == "Nie"
    assert ImportPracownikowRow._porownaj_bool(None, None)["plik"] == ""


def test_porownaj_bool_rozne_gdy_plik_inny_niz_baza():
    wynik = ImportPracownikowRow._porownaj_bool(True, False)
    assert wynik["rozne"] is True
    assert wynik["plik"] == "Tak"
    assert wynik["baza"] == "Nie"


def test_porownaj_bool_zgodne_gdy_takie_same():
    assert ImportPracownikowRow._porownaj_bool(True, True)["rozne"] is False


def test_porownaj_bool_niepodswietla_gdy_plik_none():
    # plik nie mówi nic (None) → to nie różnica, choćby baza miała False.
    assert ImportPracownikowRow._porownaj_bool(None, False)["rozne"] is False


def test_porownaj_bool_niepodswietla_bez_kontekstu_bazy():
    assert ImportPracownikowRow._porownaj_bool(True, None, ma_baze=False)["rozne"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py -v`
Expected: FAIL with `AttributeError: ... has no attribute '_porownaj_fk_obj'`.

- [ ] **Step 3: Write minimal implementation**

Insert directly after `_porownaj_fk` (ends line ~769 in `models.py`):

```python
    @staticmethod
    def _porownaj_fk_obj(plik_obj, baza_obj, *, ma_baze=True):
        """Trójka porównania pola FK gdy OBIE strony to gotowe obiekty FK
        (wymiar etatu / grupa pracownicza) — odróżnia się od ``_porownaj_fk``,
        które bierze skrót+id z pliku. Porównanie po pk. ``rozne`` = plik
        wskazuje wartość i baza jest inna (lub pusta). ``ma_baze=False`` (wiersz
        bez ``autor_jednostka`` → brak strony bazy) → ZAWSZE ``rozne=False``
        (jak ``ma_okres`` w ``_porownaj_data``: nie ma z czym porównać)."""
        plik_pk = plik_obj.pk if plik_obj else None
        baza_pk = baza_obj.pk if baza_obj else None
        rozne = ma_baze and plik_pk is not None and baza_pk != plik_pk
        return {
            "plik": str(plik_obj) if plik_obj else "",
            "baza": str(baza_obj) if baza_obj else "",
            "rozne": rozne,
        }

    @staticmethod
    def _porownaj_bool(plik_bool, baza_bool, *, ma_baze=True):
        """Trójka porównania pola bool (podstawowe miejsce pracy): ``plik`` /
        ``baza`` renderują ``Tak`` / ``Nie`` / ``""`` dla ``True`` / ``False`` /
        ``None``. ``rozne`` = plik JAWNIE mówi (``not None``) i różni się od bazy.
        ``None`` w pliku = „plik nie mówi nic" → nie różnica. ``ma_baze=False``
        → ``rozne=False`` (brak strony bazy do porównania)."""

        def _etykieta(v):
            return "" if v is None else ("Tak" if v else "Nie")

        rozne = ma_baze and plik_bool is not None and plik_bool != baza_bool
        return {
            "plik": _etykieta(plik_bool),
            "baza": _etykieta(baza_bool),
            "rozne": rozne,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py
git commit -m "feat(import): komparatory _porownaj_fk_obj / _porownaj_bool dla pól zatrudnienia"
```

---

## Task 2: `ma_kolumne_*` parent properties

**Files:**
- Modify: `src/import_pracownikow/models.py` (next to `ma_kolumne_stanowiska`, line 534)
- Test: `src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py`

**Interfaces:**
- Produces (on `ImportPracownikow` parent model):
  - `ma_kolumne_wymiaru -> bool` — `True` if `wymiar_etatu_tekst` OR `wymiar_etatu_ulamek` in `mapowanie_kolumn.values()`.
  - `ma_kolumne_grupy -> bool` — `True` if `grupa_pracownicza` in values.
  - `ma_kolumne_podstawowego -> bool` — `True` if `podstawowe_miejsce_pracy` in values.
- Consumes: nothing.

- [ ] **Step 1: Write the failing tests**

```python
# append to test_porownywarka_zatrudnienie.py

@pytest.mark.django_db
def test_ma_kolumne_wymiaru_dla_tekstu_i_ulamka():
    imp = baker.make(
        "import_pracownikow.ImportPracownikow",
        mapowanie_kolumn={"Etat": "wymiar_etatu_tekst"},
    )
    assert imp.ma_kolumne_wymiaru is True
    imp.mapowanie_kolumn = {"Wymiar": "wymiar_etatu_ulamek"}
    assert imp.ma_kolumne_wymiaru is True
    imp.mapowanie_kolumn = {"Coś": "email"}
    assert imp.ma_kolumne_wymiaru is False


@pytest.mark.django_db
def test_ma_kolumne_grupy_i_podstawowego():
    imp = baker.make(
        "import_pracownikow.ImportPracownikow",
        mapowanie_kolumn={
            "Grupa": "grupa_pracownicza",
            "Gł. zakład": "podstawowe_miejsce_pracy",
        },
    )
    assert imp.ma_kolumne_grupy is True
    assert imp.ma_kolumne_podstawowego is True
    imp.mapowanie_kolumn = {}
    assert imp.ma_kolumne_grupy is False
    assert imp.ma_kolumne_podstawowego is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py -k ma_kolumne -v`
Expected: FAIL with `AttributeError: ... 'ImportPracownikow' object has no attribute 'ma_kolumne_wymiaru'`.

- [ ] **Step 3: Write minimal implementation**

Insert after `ma_kolumne_stanowiska` (line 538):

```python
    @property
    def ma_kolumne_wymiaru(self):
        """Czy plik ma kolumnę wymiaru etatu (zmapowaną na ``wymiar_etatu_tekst``
        LUB ``wymiar_etatu_ulamek`` — mapping.py rozbija wymiar na dwa cele).
        Steruje pokazaniem wiersza „Wymiar etatu" w karcie porównań."""
        cele = set((self.mapowanie_kolumn or {}).values())
        return bool(cele & {"wymiar_etatu_tekst", "wymiar_etatu_ulamek"})

    @property
    def ma_kolumne_grupy(self):
        """Mirror ``ma_kolumne_wymiaru`` dla grupy pracowniczej."""
        return "grupa_pracownicza" in (self.mapowanie_kolumn or {}).values()

    @property
    def ma_kolumne_podstawowego(self):
        """Mirror ``ma_kolumne_wymiaru`` dla podstawowego miejsca pracy."""
        return "podstawowe_miejsce_pracy" in (self.mapowanie_kolumn or {}).values()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py -k ma_kolumne -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py
git commit -m "feat(import): ma_kolumne_wymiaru/grupy/podstawowego na modelu importu"
```

---

## Task 3: Extend `porownaj_z_baza()` with wymiar / grupa / podstawowe

**Files:**
- Modify: `src/import_pracownikow/models.py` — `porownaj_z_baza()` return dict (line 886-925)
- Test: `src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py`

**Interfaces:**
- Consumes: `_porownaj_fk_obj`, `_porownaj_bool` (Task 1).
- Produces: `porownaj_z_baza()` return dict gains keys `wymiar`, `grupa`, `podstawowe`, each a `{plik, baza, rozne}` triple.
  - File side = the row's own `self.wymiar_etatu` / `self.grupa_pracownicza` / `self.podstawowe_miejsce_pracy`.
  - Base side = `aj.wymiar_etatu` / `aj.grupa_pracownicza` / `aj.podstawowe_miejsce_pracy` where `aj = self.autor_jednostka`.
  - `ma_baze = aj is not None` (unmatched/deferred rows have no base → no false highlight).

- [ ] **Step 1: Write the failing tests**

```python
# append to test_porownywarka_zatrudnienie.py

@pytest.mark.django_db
def test_porownaj_z_baza_wymiar_grupa_podstawowe_rozne():
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")
    aj = baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=False,
    )
    row = baker.make(
        "import_pracownikow.ImportPracownikowRow",
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=True,
        dane_znormalizowane={},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["wymiar"]["rozne"] is True
    assert wynik["grupa"]["rozne"] is True
    assert wynik["podstawowe"]["rozne"] is True
    assert wynik["podstawowe"]["plik"] == "Tak"
    assert wynik["podstawowe"]["baza"] == "Nie"


@pytest.mark.django_db
def test_porownaj_z_baza_wymiar_zgodny():
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")
    wymiar = baker.make("bpp.Wymiar_Etatu")
    aj = baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        wymiar_etatu=wymiar,
    )
    row = baker.make(
        "import_pracownikow.ImportPracownikowRow",
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        wymiar_etatu=wymiar,
        dane_znormalizowane={},
    )
    assert row.porownaj_z_baza()["wymiar"]["rozne"] is False


@pytest.mark.django_db
def test_porownaj_z_baza_bez_aj_nie_podswietla_zatrudnienia():
    # Wiersz bez autor_jednostka: strona bazy pusta, ma_baze=False → brak
    # fałszywego podświetlenia, choć plik ma wartości.
    row = baker.make(
        "import_pracownikow.ImportPracownikowRow",
        autor=None,
        autor_jednostka=None,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=True,
        dane_znormalizowane={},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["wymiar"]["rozne"] is False
    assert wynik["grupa"]["rozne"] is False
    assert wynik["podstawowe"]["rozne"] is False
    # ale wartość z pliku nadal widoczna:
    assert wynik["podstawowe"]["plik"] == "Tak"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py -k porownaj_z_baza -v`
Expected: FAIL with `KeyError: 'wymiar'`.

- [ ] **Step 3: Write minimal implementation**

In `porownaj_z_baza()`, add three keys to the returned dict (after `"data_do": …` at line 919-924, before the closing `}`). Note `aj` is already bound at line 862:

```python
            "wymiar": self._porownaj_fk_obj(
                self.wymiar_etatu,
                aj.wymiar_etatu if aj else None,
                ma_baze=aj is not None,
            ),
            "grupa": self._porownaj_fk_obj(
                self.grupa_pracownicza,
                aj.grupa_pracownicza if aj else None,
                ma_baze=aj is not None,
            ),
            "podstawowe": self._porownaj_bool(
                self.podstawowe_miejsce_pracy,
                aj.podstawowe_miejsce_pracy if aj else None,
                ma_baze=aj is not None,
            ),
```

Also extend the docstring's field list (line 851-852) to mention wymiaru etatu / grupy pracowniczej / podstawowego miejsca pracy.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py -v`
Expected: PASS (all).

Also run the existing comparator suite to confirm no regression:
Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka.py src/import_pracownikow/tests/test_stany_pol.py -v`
Expected: PASS (unchanged — new keys are additive, `POLA_ROZNIC` untouched).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_porownywarka_zatrudnienie.py
git commit -m "feat(import): porownaj_z_baza zwraca wymiar/grupa/podstawowe miejsce pracy"
```

---

## Task 4: Render three grid rows in `_wiersz_preview_kom.html`

**Files:**
- Modify: `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html` (after the Stanowisko dyd. block, line 234-239)
- Test: `src/import_pracownikow/tests/test_views_preview_render.py`

**Interfaces:**
- Consumes: `porownanie.wymiar` / `.grupa` / `.podstawowe` (Task 3); `parent_object.ma_kolumne_wymiaru` / `.ma_kolumne_grupy` / `.ma_kolumne_podstawowego` (Task 2).
- Produces: HTML — three `import-porownanie-item` blocks, each wrapped in the matching `ma_kolumne_*` conditional.

- [ ] **Step 1: Write the failing test**

Locate the existing render helper in `test_views_preview_render.py` (it renders a preview row via the view/client). Add tests that a mapped column shows the row and an unmapped column hides it. Follow the file's existing fixture/client pattern for building an analysed import; here is the assertion shape (adapt setup to the file's helpers):

```python
# append to test_views_preview_render.py — adapt _zbuduj_podglad(...) to the
# file's existing helper for an analysed import with one preview row.

@pytest.mark.django_db
def test_grid_pokazuje_wiersze_zatrudnienia_gdy_zmapowane(client_zalogowany):
    imp = _zbuduj_podglad(
        mapowanie_kolumn={
            "Etat": "wymiar_etatu_tekst",
            "Grupa": "grupa_pracownicza",
            "Gł. zakład": "podstawowe_miejsce_pracy",
        },
    )
    html = _render_podglad(client_zalogowany, imp)
    assert "Wymiar etatu:" in html
    assert "Grupa prac.:" in html
    assert "Podst. miejsce:" in html


@pytest.mark.django_db
def test_grid_ukrywa_wiersze_zatrudnienia_gdy_niezmapowane(client_zalogowany):
    imp = _zbuduj_podglad(mapowanie_kolumn={"E-mail": "email"})
    html = _render_podglad(client_zalogowany, imp)
    assert "Wymiar etatu:" not in html
    assert "Grupa prac.:" not in html
    assert "Podst. miejsce:" not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py -k zatrudnienia -v`
Expected: FAIL (`"Wymiar etatu:" in html` is False — markup not yet added).

- [ ] **Step 3: Write minimal implementation**

Insert after the `{% if parent_object.ma_kolumne_stanowiska %}` block (closes line 239), still inside `{% with porownanie=… %}`:

```django
                    {% if parent_object.ma_kolumne_wymiaru %}
                        <div class="import-porownanie-item">
                            <span class="import-porownanie-etykieta">Wymiar etatu:</span>
                            {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.wymiar %}
                        </div>
                    {% endif %}
                    {% if parent_object.ma_kolumne_grupy %}
                        <div class="import-porownanie-item">
                            <span class="import-porownanie-etykieta">Grupa prac.:</span>
                            {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.grupa %}
                        </div>
                    {% endif %}
                    {% if parent_object.ma_kolumne_podstawowego %}
                        <div class="import-porownanie-item">
                            <span class="import-porownanie-etykieta">Podst. miejsce:</span>
                            {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.podstawowe %}
                        </div>
                    {% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html src/import_pracownikow/tests/test_views_preview_render.py
git commit -m "feat(import): trzy wiersze zatrudnienia w karcie porównań (warunkowo od mapowania)"
```

---

## Task 5: Match / Create / Skip radio group for `brak` rows

**Files:**
- Modify: `src/import_pracownikow/views.py` — `PrzelaczUtworzNowegoView.post` (line 471-482)
- Modify: `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html` — replace `brak` branch (line 70-102)
- Test: `src/import_pracownikow/tests/test_views_utworz_nowego.py`, `tests/test_views_preview_render.py`

**Interfaces:**
- The radio group has three options sharing one visual group; persistent server state is the existing `utworz_nowego` bool + `autor` FK (NO new field):
  - **Pomiń — nie importuj** (default): `utworz_nowego=False`, `autor=None`.
  - **Utwórz nowego autora**: POST `wybor=utworz` → `utworz_nowego=True`.
  - **Dopasuj do istniejącego**: reveals the lazy Select2; picking POSTs to `dopasuj-autora` (unchanged), which binds `autor` and transitions the row out of `brak`.
- View tweak: `PrzelaczUtworzNowegoView.post` reads `wybor` (`"utworz"` → True, `"pomin"`/anything else → False). Keep backward-accepting the legacy `utworz_nowego` param so the change is minimal and the existing test can migrate cleanly.

Why radios not a checkbox: "Skip" being an **explicit, labelled default** is the whole point — it stops rows being silently lost. Selecting "Dopasuj" is a client-only reveal; the actual match still flows through `DopasujAutoraView`, so `brak`→matched transition logic is untouched.

- [ ] **Step 1: Write the failing view tests**

Read `test_views_utworz_nowego.py` first (it's short — 1.9K) to reuse its fixture. Add:

```python
# in test_views_utworz_nowego.py

@pytest.mark.django_db
def test_wybor_utworz_ustawia_flage(client_zalogowany, wiersz_brak):
    url = reverse(
        "import_pracownikow:utworz-nowego",
        args=[wiersz_brak.parent_id, wiersz_brak.pk],
    )
    resp = client_zalogowany.post(url, {"wybor": "utworz"})
    assert resp.status_code == 200
    wiersz_brak.refresh_from_db()
    assert wiersz_brak.utworz_nowego is True


@pytest.mark.django_db
def test_wybor_pomin_kasuje_flage(client_zalogowany, wiersz_brak):
    wiersz_brak.utworz_nowego = True
    wiersz_brak.save(update_fields=["utworz_nowego"])
    url = reverse(
        "import_pracownikow:utworz-nowego",
        args=[wiersz_brak.parent_id, wiersz_brak.pk],
    )
    resp = client_zalogowany.post(url, {"wybor": "pomin"})
    assert resp.status_code == 200
    wiersz_brak.refresh_from_db()
    assert wiersz_brak.utworz_nowego is False
```

If `wiersz_brak` fixture does not exist in that file, define it locally (confidence `STATUS_BRAK`, no autor). Also update any existing test in the file that posts `{"utworz_nowego": "on"}` to instead post `{"wybor": "utworz"}` (or keep both if you retain legacy acceptance — see Step 3).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_views_utworz_nowego.py -v`
Expected: FAIL (`utworz_nowego` stays False — view doesn't yet read `wybor`).

- [ ] **Step 3: Update the view**

Replace the state-setting line in `PrzelaczUtworzNowegoView.post` (line 480):

```python
        # Radio grupy Pomiń/Utwórz/Dopasuj: „utworz" → flaga True, cokolwiek
        # innego (Pomiń) → False. Legacy param `utworz_nowego` (checkbox) nadal
        # akceptowany, żeby stary HTMX/testy nie padły.
        wybor = request.POST.get("wybor")
        if wybor is not None:
            row.utworz_nowego = wybor == "utworz"
        else:
            row.utworz_nowego = request.POST.get("utworz_nowego") is not None
        row.save(update_fields=["utworz_nowego"])
```

- [ ] **Step 4: Run view tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_views_utworz_nowego.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing render test**

```python
# in test_views_preview_render.py

@pytest.mark.django_db
def test_brak_row_pokazuje_radio_pomin_utworz_dopasuj(client_zalogowany):
    imp = _zbuduj_podglad_z_wierszem_brak()
    html = _render_podglad(client_zalogowany, imp)
    assert 'value="pomin"' in html
    assert 'value="utworz"' in html
    assert 'value="dopasuj"' in html
    assert "Pomiń — nie importuj" in html
    assert "Utwórz nowego autora" in html
    assert "Dopasuj do istniejącego" in html
```

- [ ] **Step 6: Run render test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py -k radio -v`
Expected: FAIL.

- [ ] **Step 7: Replace the `brak` branch markup**

Replace lines 70-102 (the `{% elif row.confidence == "brak" %}` body, up to but not including `{% else %}` at line 103) with the radio group below. It keeps the existing lazy-Select2 machinery (`.js-zmien-autora` / `.js-autor-picker` — the shared script at 129-186 is untouched). The "Dopasuj" radio reveals the picker via a tiny change listener; Pomiń/Utwórz POST to `utworz-nowego`:

```django
                {% elif row.confidence == "brak" %}
                    {# D2: jawny wybór Pomiń / Utwórz / Dopasuj zamiast #}
                    {# zakopanego linku + checkboxa. „Pomiń" to widoczny #}
                    {# domyślny stan — żeby wiersz nie zniknął po cichu. #}
                    <form class="import-brak-wybor"
                          method="post"
                          hx-post="{% url "import_pracownikow:utworz-nowego" parent_object.pk row.pk %}"
                          hx-target="#wiersz-{{ row.pk }}"
                          hx-swap="innerHTML"
                          hx-trigger="change from:.js-brak-radio-post">
                        {% csrf_token %}
                        <label>
                            <input type="radio" name="wybor" value="pomin"
                                   class="js-brak-radio-post"
                                   {% if not row.utworz_nowego %}checked{% endif %}>
                            <span class="fi-prohibited"></span>
                            Pomiń — nie importuj
                        </label>
                        <label>
                            <input type="radio" name="wybor" value="utworz"
                                   class="js-brak-radio-post"
                                   {% if row.utworz_nowego %}checked{% endif %}>
                            <span class="fi-plus"></span>
                            Utwórz nowego autora
                        </label>
                        <label>
                            <input type="radio" name="wybor" value="dopasuj"
                                   class="js-brak-radio-dopasuj">
                            <span class="fi-magnifying-glass"></span>
                            Dopasuj do istniejącego
                        </label>
                    </form>
                    {# „Dopasuj" odsłania leniwy Select2 (jak dawny link). #}
                    {# Wybór autora POST-uje do dopasuj-autora (bez zmian) i #}
                    {# przenosi wiersz poza „brak". #}
                    <div class="import-autor-zmien">
                        <div class="js-autor-picker" hidden>
                            <form method="post"
                                  hx-post="{% url "import_pracownikow:dopasuj-autora" parent_object.pk row.pk %}"
                                  hx-target="#wiersz-{{ row.pk }}"
                                  hx-swap="innerHTML"
                                  hx-trigger="change">
                                {% csrf_token %}
                                <select name="autor"
                                        data-autocomplete-url="{% url "bpp:import-autor-autocomplete" %}"></select>
                            </form>
                        </div>
                    </div>
```

Then extend the shared picker `<script>` (line 129-186) so the "Dopasuj" radio reveals + inits the Select2. Add this inside the IIFE, alongside the existing `.js-zmien-autora` click handler (delegation, idempotent under the `window.__bppImportAutorPicker` guard):

```javascript
                    document.addEventListener("change", function (e) {
                        var radio = e.target.closest(".js-brak-radio-dopasuj");
                        if (!radio || !radio.checked) return;
                        var akcje = radio.closest(".import-autor-akcje");
                        var wrap = akcje &&
                            akcje.querySelector(".js-autor-picker");
                        if (!wrap) return;
                        wrap.hidden = false;
                        initPicker(wrap);
                    });
```

Note: The `hx-trigger="change from:.js-brak-radio-post"` on the Pomiń/Utwórz form ensures picking "Dopasuj" (class `js-brak-radio-dopasuj`) does NOT fire the `utworz-nowego` POST — only Pomiń/Utwórz do. This keeps `utworz_nowego=False` while the user is mid-match.

- [ ] **Step 8: Run render + view tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py src/import_pracownikow/tests/test_views_utworz_nowego.py src/import_pracownikow/tests/test_dopasuj_autora.py -v`
Expected: PASS (dopasuj-autora transition still works — its view is unchanged).

- [ ] **Step 9: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html src/import_pracownikow/tests/test_views_utworz_nowego.py src/import_pracownikow/tests/test_views_preview_render.py
git commit -m "feat(import): radio Pomiń/Utwórz/Dopasuj dla wierszy bez dopasowania"
```

---

## Task 6: Finalize guard (warn, allow proceed)

**Files:**
- Modify: `src/import_pracownikow/models.py` — add parent count method (near `liczniki_ludzi_z_xls`, line 459)
- Create: `src/import_pracownikow/templates/import_pracownikow/partials/_ostrzezenie_brak_dopasowania.html`
- Modify: `src/import_pracownikow/templates/import_pracownikow/przeglad.html` — include partial + `confirm()` on finalize button (line 190-201)
- Test: `src/import_pracownikow/tests/test_przeglad.py`

**Interfaces:**
- Produces: `ImportPracownikow.liczba_wierszy_do_pominiecia() -> int` — count of rows that will be silently skipped at commit: `autor_id IS NULL AND utworz_nowego=False`. (This is the exact "will be skipped" predicate, independent of the `confidence` label.)

- [ ] **Step 1: Write the failing tests**

```python
# in test_przeglad.py (or a focused test_finalize_guard.py)

@pytest.mark.django_db
def test_liczba_wierszy_do_pominiecia_liczy_nierozwiazane():
    imp = baker.make("import_pracownikow.ImportPracownikow")
    # pominięty: brak autora, bez utworz_nowego
    baker.make(
        "import_pracownikow.ImportPracownikowRow",
        parent=imp, autor=None, utworz_nowego=False,
    )
    # NIE liczony: utworz_nowego=True
    baker.make(
        "import_pracownikow.ImportPracownikowRow",
        parent=imp, autor=None, utworz_nowego=True,
    )
    # NIE liczony: ma autora
    baker.make(
        "import_pracownikow.ImportPracownikowRow",
        parent=imp, autor=baker.make("bpp.Autor"), utworz_nowego=False,
    )
    assert imp.liczba_wierszy_do_pominiecia() == 1


@pytest.mark.django_db
def test_hub_pokazuje_ostrzezenie_gdy_sa_pominiete(client_zalogowany):
    imp = _zbuduj_hub_z_pominietymi(n=2)  # adapt to test_przeglad.py helpers
    html = _render_hub(client_zalogowany, imp)
    assert "2 osób bez dopasowania zostanie pominiętych" in html


@pytest.mark.django_db
def test_hub_bez_ostrzezenia_gdy_wszystko_rozwiazane(client_zalogowany):
    imp = _zbuduj_hub_bez_pominietych()
    html = _render_hub(client_zalogowany, imp)
    assert "bez dopasowania zostanie pominiętych" not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_przeglad.py -k pominie -v`
Expected: FAIL (`AttributeError: liczba_wierszy_do_pominiecia`).

- [ ] **Step 3: Add the count method**

In `ImportPracownikow` (after `liczniki_ludzi_z_xls`, line 480):

```python
    def liczba_wierszy_do_pominiecia(self):
        """Ile wierszy zostanie PO CICHU pominiętych przy zapisie osób: brak
        dopasowanego autora (``autor IS NULL``) i BEZ decyzji „Utwórz nowego"
        (``utworz_nowego=False``). Zasila ostrzeżenie finalizacji na hubie —
        ostrzega, NIE blokuje (świadoma decyzja usera)."""
        return self.importpracownikowrow_set.filter(
            autor__isnull=True, utworz_nowego=False
        ).count()
```

- [ ] **Step 4: Create the warning partial**

`src/import_pracownikow/templates/import_pracownikow/partials/_ostrzezenie_brak_dopasowania.html`:

```django
{# Ostrzeżenie finalizacji: N wierszy bez dopasowania (brak autora, bez #}
{# „Utwórz nowego") zostanie pominiętych przy zapisie osób. Ostrzega, NIE #}
{# blokuje. Renderowane tylko gdy licznik > 0. #}
<div class="callout warning">
    <p>
        <span class="fi-alert"></span>
        <strong>{{ liczba_pominietych }} os{{ liczba_pominietych|pluralize:"oba,oby,ób" }} bez dopasowania zostanie pominiętych</strong>
        (nie zostaną zaimportowane). Wróć do tabeli i dla każdej wybierz
        „Utwórz nowego autora" albo „Dopasuj do istniejącego", jeśli mają
        trafić do bazy.
    </p>
</div>
```

Note: the test asserts the substring `"N osób bez dopasowania zostanie pominiętych"`. Verify the `pluralize` output for the test's `n` (for n=2 Polish → "osób"); if the filter's form differs, simplify the partial to a plain `{{ liczba_pominietych }} osób bez dopasowania zostanie pominiętych` to keep the copy stable and the test deterministic.

- [ ] **Step 5: Wire into the hub + confirm()**

In `przeglad.html`, immediately after the `_ostrzezenie_podstawowe_miejsce.html` include (line 190), add:

```django
                    {% if parent_object.liczba_wierszy_do_pominiecia %}
                        {% include "import_pracownikow/partials/_ostrzezenie_brak_dopasowania.html" with liczba_pominietych=parent_object.liczba_wierszy_do_pominiecia %}
                    {% endif %}
```

And on the finalize `<form>` (line 191-192), add a confirm guard that only prompts when there are rows to skip. Change the form open tag to:

```django
                    <form method="post"
                          action="{% url "import_pracownikow:zatwierdz" parent_object.pk %}"
                          {% if parent_object.liczba_wierszy_do_pominiecia %}onsubmit="return confirm('{{ parent_object.liczba_wierszy_do_pominiecia }} os. bez dopasowania zostanie pominiętych. Kontynuować zapis?');"{% endif %}>
```

(`liczba_wierszy_do_pominiecia` is a method with no args → Django template calls it automatically; it runs one COUNT query per render — acceptable on the hub.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_przeglad.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/templates/import_pracownikow/partials/_ostrzezenie_brak_dopasowania.html src/import_pracownikow/templates/import_pracownikow/przeglad.html src/import_pracownikow/tests/test_przeglad.py
git commit -m "feat(import): ostrzeżenie finalizacji o wierszach do pominięcia (warn, nie blokuj)"
```

---

## Task 7: Newsfragment + full-suite verification

**Files:**
- Create: `src/bpp/newsfragments/import-widocznosc-zatrudnienia.feature.rst`

- [ ] **Step 1: Write the newsfragment**

```rst
Podgląd importu pracowników pokazuje teraz zmiany wymiaru etatu, grupy
pracowniczej i podstawowego miejsca pracy (gdy kolumny są zmapowane), a wiersze
bez dopasowania mają jawny wybór „Pomiń / Utwórz nowego / Dopasuj". Przed
zapisem osób hub ostrzega, ile wierszy bez dopasowania zostanie pominiętych.
```

- [ ] **Step 2: Run the app-scoped suite + lint**

Run: `uv run pytest src/import_pracownikow/ -q`
Expected: PASS (whole `import_pracownikow` suite green).

Run: `ruff format src/import_pracownikow/ && ruff check src/import_pracownikow/`
Expected: no changes / no errors (fix any ≤88-char or lint issues manually — do NOT batch-autofix).

- [ ] **Step 3: Commit**

```bash
git add src/bpp/newsfragments/import-widocznosc-zatrudnienia.feature.rst
git commit -m "docs(import): newsfragment — widoczność zatrudnienia + rozwiązywanie braku dopasowania"
```

---

## Manual recovery note (out of scope for code, documented for the operator)

For the stuck import `1f1ce877…` (already `zintegrowany`, 2 no-match rows): recovery is **Restart analizy → pick „Utwórz nowego" on the 2 rows → re-run**. Idempotent; only the 2 new authors get created. No code change delivers this — it's an operator action enabled by Section 2's explicit radio.

---

## Self-Review

**1. Spec coverage:**
- Section 1 (3 employment fields in grid) → Tasks 1 (comparators), 2 (`ma_kolumne_*`), 3 (`porownaj_z_baza`), 4 (template rows). ✅
- Section 1 "display-only, not in field-state filter" → Global Constraints + Task 3 Step 4 asserts `POLA_ROZNIC`/`stany_pol` untouched. ✅
- Section 2 (Match/Create/Skip radio) → Task 5. Reuses `utworz_nowego` + `DopasujAutoraView`, no new field. ✅
- Section 3 (finalize warn, allow proceed) → Task 6. Count + partial + `confirm()`, non-blocking. ✅
- Testing (comparator units incl. conditional rendering, radio view tests, finalize-guard) → Tasks 1-6 each TDD; conditional rendering in Task 4. ✅
- Newsfragment → Task 7. ✅

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Test helper names (`_zbuduj_podglad`, `_render_hub`, `client_zalogowany`, `wiersz_brak`) are flagged as "adapt to the file's existing helpers" — the implementer must read the target test file first (noted inline). This is intentional: the exact fixture names live in those files and must not be invented.

**3. Type consistency:**
- `_porownaj_fk_obj` / `_porownaj_bool` signatures identical across Tasks 1 and 3. ✅
- `ma_kolumne_wymiaru`/`grupy`/`podstawowego` identical across Tasks 2 and 4. ✅
- `liczba_wierszy_do_pominiecia` identical across Task 6 model, template, and confirm(). ✅
- Return-dict keys `wymiar`/`grupa`/`podstawowe` consistent Task 3 → Task 4. ✅
