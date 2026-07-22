# Import: słowniki stopień/stanowisko — Plan 1: Fundament domenowy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać do domeny BPP dwa słowniki — `StopienSluzbowy` (FK na `Autor`) i `StanowiskoDydaktyczne` (FK na `Autor_Jednostka`) — wraz z adminem i pozycjami w menu „Dane systemowe".

**Architecture:** Oba modele dziedziczą po `bpp.models.abstract.naming.NazwaISkrot` (nazwa unique 512 + skrot unique 128), dokładnie jak `Tytul`/`Funkcja_Autora`. FK-i używają referencji stringowej (`"bpp.StopienSluzbowy"`) i `on_delete=SET_NULL` (precedens: `Autor_Jednostka.grupa_pracownicza`/`wymiar_etatu`). Admin przez istniejący `NazwaISkrotAdmin`; menu przez listę `SYSTEM_MENU_2` w `django_bpp/menu.py`.

**Tech Stack:** Django, pytest + `@pytest.mark.django_db`, `model_bakery.baker`, pytest-testcontainers (PostgreSQL), ruff.

**Spec:** `docs/superpowers/specs/2026-07-12-import-slowniki-stopnie-stanowiska-design.md` (§4, §7 nazewnictwo, §17 on_delete)

## Global Constraints

- **ZAWSZE `uv run`** przed każdą komendą Python (`uv run python …`, `uv run pytest …`). NIGDY gołe `python`/`pytest`.
- **Max długość linii: 88 znaków** (ruff).
- **Nazwy modeli w CamelCase:** `StopienSluzbowy`, `StanowiskoDydaktyczne` (decyzja użytkownika; URL-e admina lowercase: `/admin/bpp/stopiensluzbowy/`, `/admin/bpp/stanowiskodydaktyczne/`).
- **FK słowników:** referencja stringowa (`"bpp.StopienSluzbowy"`, `"bpp.StanowiskoDydaktyczne"`), `on_delete=SET_NULL, null=True, blank=True`.
- **NIE modyfikować wydanych migracji.** Nowa migracja `bpp` = następny numer po `0467` → `0468`.
- **NIE odświeżać baseline** (`baseline-sql/`) w tym branchu — refresh dopiero przy scalaniu do `dev`.
- **Testy:** wyłącznie konwencje pytest (funkcje, brak `unittest.TestCase`), `baker.make` do obiektów DB. DB dostarcza pytest-testcontainers (wymaga działającego Dockera; przy OrbStack: `export DOCKER_HOST=unix:///Users/mpasternak/.orbstack/run/docker.sock`).
- **Branch:** `feat/import-pracownikow-slowniki-stopnie-stanowiska` (już utworzony od `dev`).

## Roadmap (4 plany; ten dokument = Plan 1)

1. **Plan 1 — Fundament domenowy** (ten plik): modele `StopienSluzbowy`/`StanowiskoDydaktyczne`, FK, migracja `bpp 0468`, admin, menu. → działające słowniki w adminie.
2. **Plan 2 — import_common + parsery + mapowanie**: klasyfikatory `stopien`/`stanowisko`/`jednostka_niepelna`, parsery komórki i „nazwisko imię", cele/synonimy mapowania + reguła kontekstowa `stopień` + walidacja, profil „ostatnio użyty". → czyste funkcje testowalne jednostkowo.
3. **Plan 3 — Pipeline + ekrany weryfikacji**: modele decyzji + migracja `import_pracownikow 0023`, `AutorForm`, reconcilery, analyze/integrate, widoki/szablony weryfikacji, bramki, wpięcie parserów (komórka, nazwisko-imię, niepełna nazwa). → E2E weryfikacja słowników i dopięcie do osób.
4. **Plan 4 — Email (łagodna walidacja) + porównywarka + E2E + newsfragment**: łagodny e-mail + kolumny porównywarki plik-vs-baza (e-mail/stopień/stanowisko), pełny test E2E na `struktura.xlsx`, newsfragment podsumowujący feature.

---

## File Structure (Plan 1)

- Modify: `src/bpp/models/autor.py` — dodaj klasy `StopienSluzbowy`, `StanowiskoDydaktyczne`; FK `Autor.stopien_sluzbowy`, `Autor_Jednostka.stanowisko`.
- Create: `src/bpp/migrations/0468_stopien_sluzbowy_stanowisko_dydaktyczne.py` — auto-generowana przez `makemigrations`.
- Modify: `src/bpp/admin/__init__.py` — import + rejestracja obu słowników przez `NazwaISkrotAdmin`.
- Modify: `src/bpp/admin/autor.py` — `stopien_sluzbowy` w `AutorForm.Meta.fields`; `stanowisko` w `Autor_JednostkaInlineForm.Meta.fields`.
- Modify: `src/django_bpp/menu.py` — 2 pozycje w `SYSTEM_MENU_2`.
- Create: `src/bpp/tests/test_models_stopien_stanowisko.py` — testy modeli.
- Create: `src/bpp/tests/test_admin_stopien_stanowisko.py` — testy adminu/formularzy.
- Modify: `src/django_bpp/tests/test_menu.py` — test nowych pozycji menu.

---

## Task 1: Modele `StopienSluzbowy` + `StanowiskoDydaktyczne` + FK + migracja

**Files:**
- Test: `src/bpp/tests/test_models_stopien_stanowisko.py` (create)
- Modify: `src/bpp/models/autor.py`
- Create (via makemigrations): `src/bpp/migrations/0468_stopien_sluzbowy_stanowisko_dydaktyczne.py`

**Interfaces:**
- Produces: `bpp.models.StopienSluzbowy` (NazwaISkrot: `nazwa`, `skrot`, `__str__`→nazwa, verbose_name „stopień służbowy"); `bpp.models.StanowiskoDydaktyczne` (NazwaISkrot; verbose_name „stanowisko dydaktyczne"); `Autor.stopien_sluzbowy` (FK, nullable, SET_NULL); `Autor_Jednostka.stanowisko` (FK, nullable, SET_NULL).

- [ ] **Step 1: Write the failing test**

Create `src/bpp/tests/test_models_stopien_stanowisko.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Jednostka,
    StanowiskoDydaktyczne,
    StopienSluzbowy,
)


@pytest.mark.django_db
def test_stopien_sluzbowy_str_i_verbose_name():
    s = baker.make(StopienSluzbowy, nazwa="kapitan", skrot="kpt.")
    assert str(s) == "kapitan"
    assert s._meta.verbose_name == "stopień służbowy"
    assert s._meta.verbose_name_plural == "stopnie służbowe"


@pytest.mark.django_db
def test_stanowisko_dydaktyczne_str_i_verbose_name():
    s = baker.make(StanowiskoDydaktyczne, nazwa="adiunkt", skrot="adiunkt")
    assert str(s) == "adiunkt"
    assert s._meta.verbose_name == "stanowisko dydaktyczne"
    assert s._meta.verbose_name_plural == "stanowiska dydaktyczne"


@pytest.mark.django_db
def test_autor_ma_stopien_sluzbowy():
    st = baker.make(StopienSluzbowy, nazwa="brygadier", skrot="bryg.")
    a = baker.make(Autor, stopien_sluzbowy=st)
    a.refresh_from_db()
    assert a.stopien_sluzbowy == st


@pytest.mark.django_db
def test_autor_jednostka_ma_stanowisko():
    sd = baker.make(StanowiskoDydaktyczne, nazwa="profesor", skrot="prof.")
    aj = baker.make(Autor_Jednostka, stanowisko=sd)
    aj.refresh_from_db()
    assert aj.stanowisko == sd


@pytest.mark.django_db
def test_stopien_set_null_po_skasowaniu_slownika():
    st = baker.make(StopienSluzbowy, nazwa="starszy strażak", skrot="st. str.")
    a = baker.make(Autor, stopien_sluzbowy=st)
    st.delete()
    a.refresh_from_db()
    assert a.stopien_sluzbowy is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_models_stopien_stanowisko.py -v`
Expected: FAIL — `ImportError: cannot import name 'StopienSluzbowy' from 'bpp.models'`.

- [ ] **Step 3: Dodaj klasy słowników w `src/bpp/models/autor.py`**

Wstaw obie klasy bezpośrednio PO klasie `Funkcja_Autora` (przed `Grupa_Pracownicza`), zachowując istniejący styl `Meta`:

```python
class StopienSluzbowy(NazwaISkrot):
    """Stopień służbowy (np. pożarniczy: kpt., bryg.) — słownik na autorze."""

    class Meta:
        verbose_name = "stopień służbowy"
        verbose_name_plural = "stopnie służbowe"
        ordering = ["nazwa"]
        app_label = "bpp"


class StanowiskoDydaktyczne(NazwaISkrot):
    """Stanowisko dydaktyczne (np. adiunkt, profesor) — słownik na
    powiązaniu autor-jednostka."""

    class Meta:
        verbose_name = "stanowisko dydaktyczne"
        verbose_name_plural = "stanowiska dydaktyczne"
        ordering = ["nazwa"]
        app_label = "bpp"
```

- [ ] **Step 4: Dodaj FK `Autor.stopien_sluzbowy`**

W `src/bpp/models/autor.py` w klasie `Autor`, bezpośrednio pod linią `tytul = models.ForeignKey(Tytul, CASCADE, blank=True, null=True)` dodaj:

```python
    stopien_sluzbowy = models.ForeignKey(
        "bpp.StopienSluzbowy",
        SET_NULL,
        blank=True,
        null=True,
        verbose_name="stopień służbowy",
    )
```

- [ ] **Step 5: Dodaj FK `Autor_Jednostka.stanowisko`**

W `src/bpp/models/autor.py` w klasie `Autor_Jednostka`, bezpośrednio pod linią z `funkcja = models.ForeignKey("bpp.Funkcja_Autora", CASCADE, null=True, blank=True)` dodaj:

```python
    stanowisko = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        SET_NULL,
        null=True,
        blank=True,
        verbose_name="stanowisko dydaktyczne",
    )
```

- [ ] **Step 6: Zweryfikuj eksport modeli**

`src/bpp/models/__init__.py` to `from .autor import *`, a `autor.py` NIE ma `__all__` — nowe modele eksportują się automatycznie, bez ręcznej zmiany `__init__.py`. Zweryfikuj:

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python -c "from bpp.models import StopienSluzbowy, StanowiskoDydaktyczne; print('ok')"`
Expected: `ok`.

- [ ] **Step 7: Wygeneruj migrację**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp --name stopien_sluzbowy_stanowisko_dydaktyczne`
Expected: utworzony plik `src/bpp/migrations/0468_stopien_sluzbowy_stanowisko_dydaktyczne.py` z `CreateModel` dla obu modeli + `AddField` dla `Autor.stopien_sluzbowy` i `Autor_Jednostka.stanowisko`. Zależność (`dependencies`) wskazuje na `0467_seed_crossref_mapper_rows`.

Zweryfikuj brak dryfu: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp --check --dry-run`
Expected: „No changes detected".

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_models_stopien_stanowisko.py -v`
Expected: PASS (5 testów).

- [ ] **Step 9: Commit**

```bash
git add src/bpp/models/autor.py \
  src/bpp/migrations/0468_stopien_sluzbowy_stanowisko_dydaktyczne.py \
  src/bpp/tests/test_models_stopien_stanowisko.py
git commit -m "feat(bpp): słowniki StopienSluzbowy i StanowiskoDydaktyczne + FK"
```

---

## Task 2: Admin słowników + pola w formularzach `Autor`/`Autor_Jednostka`

**Files:**
- Test: `src/bpp/tests/test_admin_stopien_stanowisko.py` (create)
- Modify: `src/bpp/admin/__init__.py`
- Modify: `src/bpp/admin/autor.py`

**Interfaces:**
- Consumes: `StopienSluzbowy`, `StanowiskoDydaktyczne` (Task 1); `NazwaISkrotAdmin` (istniejący, `src/bpp/admin/__init__.py:138`).
- Produces: rejestracja obu modeli w `admin.site`; pole `stopien_sluzbowy` w `AutorForm.base_fields`; pole `stanowisko` w `Autor_JednostkaInlineForm.base_fields`.

- [ ] **Step 1: Write the failing test**

Create `src/bpp/tests/test_admin_stopien_stanowisko.py`:

```python
from django.contrib import admin as djadmin
from django.contrib.admin.utils import flatten_fieldsets

from bpp.admin.autor import AutorAdmin, AutorForm, Autor_JednostkaInlineForm
from bpp.models import StanowiskoDydaktyczne, StopienSluzbowy


def test_slowniki_zarejestrowane_w_adminie():
    assert StopienSluzbowy in djadmin.site._registry
    assert StanowiskoDydaktyczne in djadmin.site._registry


def test_autorform_ma_pole_stopien_sluzbowy():
    assert "stopien_sluzbowy" in AutorForm.base_fields
    assert "stopien_sluzbowy" in flatten_fieldsets(AutorAdmin.fieldsets)


def test_inline_autor_jednostka_ma_pole_stanowisko():
    assert "stanowisko" in Autor_JednostkaInlineForm.base_fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin_stopien_stanowisko.py -v`
Expected: FAIL — `test_slowniki_zarejestrowane_w_adminie` (modele niezarejestrowane) oraz brak pól w formularzach.

- [ ] **Step 3: Zaimportuj i zarejestruj słowniki w adminie**

W `src/bpp/admin/__init__.py`: w bloku `from ..models import (…)` (linie ~18-31) dodaj (alfabetycznie) `StanowiskoDydaktyczne,` i `StopienSluzbowy,`. Następnie bezpośrednio POD linią `admin.site.register(Tytul, NazwaISkrotAdmin)` (linia ~145) dodaj:

```python
admin.site.register(StopienSluzbowy, NazwaISkrotAdmin)
admin.site.register(StanowiskoDydaktyczne, NazwaISkrotAdmin)
```

- [ ] **Step 4: Dodaj `stopien_sluzbowy` do `AutorForm`**

W `src/bpp/admin/autor.py`, w `AutorForm.Meta.fields`, dodaj `"stopien_sluzbowy"` bezpośrednio po `"tytul"`:

```python
        fields = [
            "pbn_id",
            "imiona",
            "nazwisko",
            "tytul",
            "stopien_sluzbowy",
            "pseudonim",
            "aktualna_funkcja",
            # … reszta bez zmian …
        ]
```

- [ ] **Step 5: Dodaj `stopien_sluzbowy` do `AutorAdmin.fieldsets`**

`AutorAdmin` używa `fieldsets` (nie `fields`), a Django buduje formularz przez `flatten_fieldsets(fieldsets)` — samo dodanie pola do `AutorForm.Meta.fields` NIE pokaże go w adminie. W `src/bpp/admin/autor.py` znajdź `class AutorAdmin` i jego atrybut `fieldsets`; w PIERWSZYM fieldsecie (`None`, ten z polem `"tytul"`) dodaj `"stopien_sluzbowy"` bezpośrednio po `"tytul"`:

```python
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "imiona",
                    "nazwisko",
                    "tytul",
                    "stopien_sluzbowy",
                    "pseudonim",
                    # … reszta bez zmian …
                )
            },
        ),
        # … pozostałe fieldsety bez zmian …
    )
```

- [ ] **Step 6: Dodaj `stanowisko` do `Autor_JednostkaInlineForm`**

W `src/bpp/admin/autor.py`, w `Autor_JednostkaInlineForm.Meta.fields`, dodaj `"stanowisko"` bezpośrednio po `"funkcja"`:

```python
        fields = [
            "autor",
            "jednostka",
            "rozpoczal_prace",
            "zakonczyl_prace",
            "funkcja",
            "stanowisko",
            "podstawowe_miejsce_pracy",
            "grupa_pracownicza",
            "wymiar_etatu",
        ]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_admin_stopien_stanowisko.py -v`
Expected: PASS (3 testy).

- [ ] **Step 8: Commit**

```bash
git add src/bpp/admin/__init__.py src/bpp/admin/autor.py \
  src/bpp/tests/test_admin_stopien_stanowisko.py
git commit -m "feat(bpp): admin dla słowników stopień/stanowisko + pola w formularzach"
```

---

## Task 3: Pozycje w menu „Dane systemowe"

**Files:**
- Modify: `src/django_bpp/menu.py`
- Modify: `src/django_bpp/tests/test_menu.py`

**Interfaces:**
- Consumes: URL-e admina z Task 2 (`/admin/bpp/stopiensluzbowy/`, `/admin/bpp/stanowiskodydaktyczne/`).
- Produces: pozycje w `SYSTEM_MENU_2`.

- [ ] **Step 1: Write the failing test**

Dodaj na końcu `src/django_bpp/tests/test_menu.py`:

```python
def test_menu_dane_systemowe_ma_nowe_slowniki():
    from django_bpp.menu import SYSTEM_MENU_2

    labels = [item[0] for item in SYSTEM_MENU_2]
    urls = [item[1] for item in SYSTEM_MENU_2]
    assert "Stopnie służbowe" in labels
    assert "Stanowiska dydaktyczne" in labels
    assert "/admin/bpp/stopiensluzbowy/" in urls
    assert "/admin/bpp/stanowiskodydaktyczne/" in urls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/django_bpp/tests/test_menu.py::test_menu_dane_systemowe_ma_nowe_slowniki -v`
Expected: FAIL — `assert "Stopnie służbowe" in labels`.

- [ ] **Step 3: Dodaj pozycje do `SYSTEM_MENU_2`**

W `src/django_bpp/menu.py`, w liście `SYSTEM_MENU_2`, zachowaj porządek alfabetyczny (Stanowiska < Statusy < Stopnie): wstaw `("Stanowiska dydaktyczne", "/admin/bpp/stanowiskodydaktyczne/")` bezpośrednio PRZED `("Statusy korekt", "/admin/bpp/status_korekty/")`, a `("Stopnie służbowe", "/admin/bpp/stopiensluzbowy/")` bezpośrednio PO niej:

```python
    ("Stanowiska dydaktyczne", "/admin/bpp/stanowiskodydaktyczne/"),
    ("Statusy korekt", "/admin/bpp/status_korekty/"),
    ("Stopnie służbowe", "/admin/bpp/stopiensluzbowy/"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/django_bpp/tests/test_menu.py -v`
Expected: PASS (nowy test + istniejące testy menu bez regresji).

- [ ] **Step 5: Commit**

```bash
git add src/django_bpp/menu.py src/django_bpp/tests/test_menu.py
git commit -m "feat(bpp): pozycje 'Stopnie służbowe' i 'Stanowiska dydaktyczne' w menu"
```

---

## Weryfikacja końcowa Planu 1

- [ ] **Step 1: Uruchom cały zestaw testów Planu 1**

Run:
```bash
uv run pytest src/bpp/tests/test_models_stopien_stanowisko.py \
  src/bpp/tests/test_admin_stopien_stanowisko.py \
  src/django_bpp/tests/test_menu.py -v 2>&1 | tee /tmp/plan1_tests.log
```
Expected: wszystkie PASS.

- [ ] **Step 2: Sanity migracji**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp --check --dry-run`
Expected: „No changes detected" (brak niezapisanych zmian modeli).

- [ ] **Step 3: ruff**

Run: `ruff check src/bpp/models/autor.py src/bpp/admin/__init__.py src/bpp/admin/autor.py src/django_bpp/menu.py src/bpp/tests/test_models_stopien_stanowisko.py src/bpp/tests/test_admin_stopien_stanowisko.py src/django_bpp/tests/test_menu.py`
Expected: brak błędów (ewentualne popraw ręcznie, bez `--fix` na masę).

- [ ] **Step 4: Newsfragment**

Create `src/bpp/newsfragments/import-slowniki-stopnie-stanowiska.feature.rst`:
```
Dodano słowniki „stopień służbowy" (na autorze) oraz „stanowisko dydaktyczne"
(na powiązaniu autor-jednostka), dostępne w panelu „Dane systemowe".
```
Commit:
```bash
git add src/bpp/newsfragments/import-slowniki-stopnie-stanowiska.feature.rst
git commit -m "docs(newsfragment): słowniki stopień służbowy / stanowisko dydaktyczne"
```

**Deliverable Planu 1:** działające słowniki `StopienSluzbowy` i `StanowiskoDydaktyczne` — edytowalne w adminie (menu „Dane systemowe"), z FK na `Autor`/`Autor_Jednostka` i migracją `bpp 0468`. Gotowe pod Plan 2 (klasyfikatory/mapowanie).
