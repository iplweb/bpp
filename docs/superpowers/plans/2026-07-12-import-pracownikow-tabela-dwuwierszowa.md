# Import pracowników — dwuwierszowa karta + filtr stanu pól — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przebudować tabelę autorów importu pracowników na dwuwierszową „kartę" (wąska, akcje mają miejsce) i dodać pasek filtrów „zmienione / zgodne / brak w pliku" per pole (6 pól, AND).

**Architecture:** Warstwa modelu liczy stan każdego pola (`stany_pol()`) — live przed integracją, ze snapshotu JSON po. Rejestr `POLA_ROZNIC` to jedno źródło prawdy (model + pasek filtrów + atrybuty `data-diff-*`). Szablon renderuje każdy rekord jako `<tbody>` z dwoma `<tr>`; filtr to czysta funkcja JS nad `<tbody>` (DataTables usunięte).

**Tech Stack:** Django 4/5, Postgres (JSONField), Foundation CSS + SCSS (grunt), HTMX, pytest + model_bakery.

## Global Constraints

- `uv run` przed KAŻDą komendą Pythona (nigdy goły `python`/`pytest`).
- Max długość linii 88 (ruff).
- NIE modyfikować WYDANYCH migracji; nowe migracje OK. Nowa migracja: `import_pracownikow/0024_*`.
- Django template comments `{# #}` jedno-liniowe (każda linia własne `{# #}`).
- Ikony: publiczny frontend → Foundation-Icons (`<span class="fi-…"/>`), nie emoji.
- NIE nadpisywać klas gridu Foundation w SCSS. Po zmianie SCSS: `grunt build`.
- Testy: pytest, standalone funkcje, `@pytest.mark.django_db`, `baker.make`.
- Zachować dosłownie w szablonie: `id="tabela-autorow"`, nagłówek „Lista modyfikacji", nagłówek kolumny „Jednostka (obecna → z pliku)" (asercje testów).
- Praca w worktree `~/Programowanie/bpp-tabela-dwuwierszowa` (branch `feat/import-pracownikow-tabela-dwuwierszowa`).
- Commity częste, po każdym zielonym kroku.

---

## Plik-mapa (co powstaje / zmienia się)

- `src/import_pracownikow/roznice.py` — **NOWY**: rejestr `POLA_ROZNIC` + ekstraktory stanu pól.
- `src/import_pracownikow/models.py` — `porownaj_z_baza()` (+tytul/+funkcja), `stany_pol()`, pole `stany_pol_snapshot`, snapshot w `integrate()`.
- `src/import_pracownikow/migrations/0024_stany_pol_snapshot.py` — **NOWY** (makemigrations).
- `src/import_pracownikow/views.py` — `ImportPracownikowResultsView.get_context_data` dokłada `pola_roznic`.
- `templates/import_pracownikow/partials/_wiersz_preview.html` — `<tr>` → `<tbody>`.
- `templates/import_pracownikow/partials/_wiersz_preview_kom.html` — dwa `<tr>` (wiersz 1 tożsamość + `data-diff-*`, wiersz 2 `colspan=5`).
- `templates/import_pracownikow/importpracownikowrow_list.html` — nowy `<thead>` (5 kol), usunięcie DataTables, pasek filtrów + JS.
- `src/bpp/static/scss/_import-pracownikow.scss` — style karty + paska filtrów.
- `src/import_pracownikow/tests/test_porownywarka.py`, `tests/test_stany_pol.py` (NOWY), `tests/test_views_preview_render.py` — testy.
- `src/bpp/newsfragments/import-tabela-dwuwierszowa.feature.rst` — **NOWY**.

---

### Task 1: `porownaj_z_baza()` — kolumny `tytul` i `funkcja`

**Files:**
- Modify: `src/import_pracownikow/models.py:745-773` (`porownaj_z_baza`)
- Test: `src/import_pracownikow/tests/test_porownywarka.py`

**Interfaces:**
- Consumes: `_porownaj_fk(plik_str, baza_obj, plik_id)` (`models.py:730`), `_porownaj_email` (`models.py:715`).
- Produces: `porownaj_z_baza()` zwraca dict z kluczami `email, stopien, stanowisko, tytul, funkcja`; każdy `{plik, baza, rozne}`. `tytul`/`funkcja` z `rozne=False` gdy brak autora/AJ (niuans zatwierdzony).

- [ ] **Step 1: Write the failing test**

Dopisz do `src/import_pracownikow/tests/test_porownywarka.py`:

```python
def test_porownaj_z_baza_tytul_rozny(db):
    from model_bakery import baker
    from import_pracownikow.models import ImportPracownikowRow

    dr = baker.make("bpp.Tytul", nazwa="doktor", skrot="dr")
    prof = baker.make("bpp.Tytul", nazwa="profesor", skrot="prof.")
    autor = baker.make("bpp.Autor", tytul=prof)
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    p = row.porownaj_z_baza()["tytul"]
    assert p["rozne"] is True
    assert p["plik"] == "dr"


def test_porownaj_z_baza_tytul_bez_autora_nie_rozny(db):
    from model_bakery import baker
    from import_pracownikow.models import ImportPracownikowRow

    dr = baker.make("bpp.Tytul", nazwa="doktor", skrot="dr")
    row = baker.make(
        ImportPracownikowRow,
        autor=None,
        tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    assert row.porownaj_z_baza()["tytul"]["rozne"] is False


def test_porownaj_z_baza_funkcja_rozna(db):
    from model_bakery import baker
    from import_pracownikow.models import ImportPracownikowRow

    stara = baker.make("bpp.Funkcja_Autora", nazwa="asystent")
    nowa = baker.make("bpp.Funkcja_Autora", nazwa="adiunkt")
    aj = baker.make("bpp.Autor_Jednostka", funkcja=stara)
    row = baker.make(
        ImportPracownikowRow,
        autor=aj.autor,
        autor_jednostka=aj,
        funkcja_autora=nowa,
        dane_znormalizowane={"stanowisko": "adiunkt"},
    )
    assert row.porownaj_z_baza()["funkcja"]["rozne"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Programowanie/bpp-tabela-dwuwierszowa && uv run pytest src/import_pracownikow/tests/test_porownywarka.py -k "tytul or funkcja" -p no:randomly -q`
Expected: FAIL — `KeyError: 'tytul'` (klucz jeszcze nie istnieje).

- [ ] **Step 3: Rozszerz `porownaj_z_baza`**

W `models.py`, w metodzie `porownaj_z_baza` (po ustaleniu `autor`/`aj`), dołóż wyliczenie baz i dwa wpisy do zwracanego dicta:

```python
        stopien_baza = (
            autor.stopien_sluzbowy if autor and autor.stopien_sluzbowy_id else None
        )
        stanowisko_baza = aj.stanowisko if aj and aj.stanowisko_id else None
        tytul_baza = autor.tytul if autor and autor.tytul_id else None
        funkcja_baza = aj.funkcja if aj and aj.funkcja_id else None
        return {
            "email": self._porownaj_email(
                dane.get("email"), autor.email if autor else ""
            ),
            "stopien": self._porownaj_fk(
                dane.get("stopień_służbowy"), stopien_baza, self.stopien_id
            ),
            "stanowisko": self._porownaj_fk(
                dane.get("stanowisko_dydaktyczne"),
                stanowisko_baza,
                self.stanowisko_dydaktyczne_id,
            ),
            # tytuł / funkcja: gdy brak autora/AJ → plik_id=None → rozne=False
            # (niuans: bez dopasowania nie podświetlamy różnicy).
            "tytul": self._porownaj_fk(
                dane.get("tytuł_stopień"),
                tytul_baza,
                self.tytul_id if autor else None,
            ),
            "funkcja": self._porownaj_fk(
                dane.get("stanowisko"),
                funkcja_baza,
                self.funkcja_autora_id if aj else None,
            ),
        }
```

Zaktualizuj też docstring metody (dopisz „tytuł naukowy i funkcję w jednostce").

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_porownywarka.py -p no:randomly -q`
Expected: PASS (nowe + istniejące).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_porownywarka.py
git commit -m "feat(import): porownaj_z_baza zwraca tytuł naukowy i funkcję w jednostce"
```

---

### Task 2: Rejestr `POLA_ROZNIC` + `stany_pol()` (live)

**Files:**
- Create: `src/import_pracownikow/roznice.py`
- Modify: `src/import_pracownikow/models.py` (dodaj metodę `stany_pol` w klasie `ImportPracownikowRow`, np. tuż po `porownaj_z_baza`)
- Test: `src/import_pracownikow/tests/test_stany_pol.py` (NOWY)

**Interfaces:**
- Consumes: `porownaj_z_baza()` (Task 1), atrybuty wiersza `jednostka_id, autor, autor_jednostka, tytul_id, funkcja_autora_id, dane_znormalizowane`.
- Produces: `POLA_ROZNIC: list[tuple[str, str, Callable]]`; `row.stany_pol() -> dict[str, str]` gdzie wartość ∈ {`"zmienione"`,`"zgodne"`,`"brak"`}. Klucze: `jednostka, email, tytul, stopien, funkcja, stanowisko`.

- [ ] **Step 1: Write the failing test**

Utwórz `src/import_pracownikow/tests/test_stany_pol.py`:

```python
import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikowRow


@pytest.mark.django_db
def test_stany_pol_jednostka_zmienione_zgodne_brak():
    jedn_stara = baker.make("bpp.Jednostka")
    jedn_nowa = baker.make("bpp.Jednostka")
    autor = baker.make("bpp.Autor")
    baker.make("bpp.Autor_Jednostka", autor=autor, jednostka=jedn_stara)
    # zmienione: autor w innej jednostce niż docelowa
    row = baker.make(
        ImportPracownikowRow, autor=autor, jednostka=jedn_nowa,
        dane_znormalizowane={},
    )
    assert row.stany_pol()["jednostka"] == "zmienione"
    # brak: jednostka odroczona
    row2 = baker.make(
        ImportPracownikowRow, autor=autor, jednostka=None, dane_znormalizowane={},
    )
    assert row2.stany_pol()["jednostka"] == "brak"


@pytest.mark.django_db
def test_stany_pol_tytul_brak_bez_autora():
    dr = baker.make("bpp.Tytul", nazwa="doktor", skrot="dr")
    row = baker.make(
        ImportPracownikowRow, autor=None, tytul=dr,
        dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    # niuans zatwierdzony: brak dopasowanego autora → "brak"
    assert row.stany_pol()["tytul"] == "brak"


@pytest.mark.django_db
def test_stany_pol_email_zgodne():
    autor = baker.make("bpp.Autor", email="a@x.pl")
    row = baker.make(
        ImportPracownikowRow, autor=autor,
        dane_znormalizowane={"email": "a@x.pl"},
    )
    assert row.stany_pol()["email"] == "zgodne"


@pytest.mark.django_db
def test_stany_pol_ma_wszystkie_klucze():
    row = baker.make(ImportPracownikowRow, autor=None, dane_znormalizowane={})
    assert set(row.stany_pol()) == {
        "jednostka", "email", "tytul", "stopien", "funkcja", "stanowisko",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_stany_pol.py -p no:randomly -q`
Expected: FAIL — `AttributeError: 'ImportPracownikowRow' object has no attribute 'stany_pol'`.

- [ ] **Step 3: Utwórz `roznice.py`**

```python
"""Rejestr pól różnic importu pracowników — jedno źródło prawdy dla
``stany_pol()`` (model), paska filtrów oraz atrybutów ``data-diff-*`` w
szablonie.

Każdy wpis: ``(klucz, etykieta, ekstraktor)``. ``ekstraktor(row) ->
"zmienione" | "zgodne" | "brak"``. Trzy stany ROZŁĄCZNE: „brak" = pole puste w
pliku (albo brak dopasowanego autora/AJ dla pól zależnych od autora);
„zmienione" = plik wskazuje wartość różną od bazy; „zgodne" = reszta.
Dodanie kolejnego pola do filtra = jeden wpis tutaj.
"""


def _dane(row):
    return row.dane_znormalizowane or {}


def _stan_jednostka(row):
    if row.jednostka_id is None:
        return "brak"
    zmienione = bool(
        row.autor_id
        and row.autor.aktualna_jednostka_id
        and row.autor.aktualna_jednostka_id != row.jednostka_id
    )
    return "zmienione" if zmienione else "zgodne"


def _stan_email(row):
    if not _dane(row).get("email"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["email"]["rozne"] else "zgodne"


def _stan_stopien(row):
    if not _dane(row).get("stopień_służbowy"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["stopien"]["rozne"] else "zgodne"


def _stan_stanowisko(row):
    if not _dane(row).get("stanowisko_dydaktyczne"):
        return "brak"
    return "zmienione" if row.porownaj_z_baza()["stanowisko"]["rozne"] else "zgodne"


def _stan_tytul(row):
    # niuans: brak dopasowanego autora → neutralne „brak" (komparator też bez
    # podświetlenia, bo porownaj_z_baza daje wtedy rozne=False).
    if row.tytul_id is None or not row.autor_id:
        return "brak"
    return "zmienione" if row.tytul_id != row.autor.tytul_id else "zgodne"


def _stan_funkcja(row):
    if row.funkcja_autora_id is None or row.autor_jednostka is None:
        return "brak"
    return (
        "zmienione"
        if row.autor_jednostka.funkcja_id != row.funkcja_autora_id
        else "zgodne"
    )


POLA_ROZNIC = [
    ("jednostka", "Jednostka", _stan_jednostka),
    ("email", "E-mail", _stan_email),
    ("tytul", "Tytuł naukowy", _stan_tytul),
    ("stopien", "Stopień służbowy", _stan_stopien),
    ("funkcja", "Funkcja w jednostce", _stan_funkcja),
    ("stanowisko", "Stanowisko dydaktyczne", _stan_stanowisko),
]
```

- [ ] **Step 4: Dodaj `stany_pol()` do modelu**

W `models.py`, w klasie `ImportPracownikowRow`, dodaj metodę (np. tuż po `porownaj_z_baza`):

```python
    def stany_pol(self):
        """Stan każdego pola różnic: ``{klucz: "zmienione"|"zgodne"|"brak"}``.
        Live wyliczenie z ``POLA_ROZNIC``. (Po integracji nadpisywane snapshotem
        — patrz ``integrate`` / pole ``stany_pol_snapshot``.)"""
        from import_pracownikow.roznice import POLA_ROZNIC

        return {klucz: ekstraktor(self) for klucz, _et, ekstraktor in POLA_ROZNIC}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_stany_pol.py -p no:randomly -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/roznice.py src/import_pracownikow/models.py src/import_pracownikow/tests/test_stany_pol.py
git commit -m "feat(import): rejestr POLA_ROZNIC + stany_pol() (live)"
```

---

### Task 3: Snapshot `stany_pol_snapshot` + migracja + zapis w `integrate()`

**Files:**
- Modify: `src/import_pracownikow/models.py` (pole na `ImportPracownikowRow`; `integrate()` `models.py:982`; `stany_pol()` z Task 2)
- Create: `src/import_pracownikow/migrations/0024_stany_pol_snapshot.py` (makemigrations)
- Test: `src/import_pracownikow/tests/test_stany_pol.py`

**Interfaces:**
- Produces: pole `stany_pol_snapshot = JSONField(null=True, blank=True)`. `stany_pol()` zwraca snapshot gdy nie-None, inaczej live. `integrate()` zapisuje snapshot PRZED mutacjami bazy.

- [ ] **Step 1: Write the failing test**

Dopisz do `test_stany_pol.py`:

```python
@pytest.mark.django_db
def test_stany_pol_snapshot_stabilny_po_integracji():
    """Po integracji baza = plik, ale snapshot pamięta że tytuł był zmieniony."""
    dr = baker.make("bpp.Tytul", nazwa="doktor", skrot="dr")
    jedn = baker.make("bpp.Jednostka")
    autor = baker.make("bpp.Autor", tytul=None)
    aj = baker.make("bpp.Autor_Jednostka", autor=autor, jednostka=jedn)
    row = baker.make(
        ImportPracownikowRow, autor=autor, autor_jednostka=aj,
        jednostka=jedn, tytul=dr, dane_znormalizowane={"tytuł_stopień": "dr"},
    )
    assert row.stany_pol()["tytul"] == "zmienione"  # live, pre-integracja
    row.zmiany_potrzebne = True
    row.integrate()
    row.refresh_from_db()
    # baza już zaktualizowana → live dałoby "zgodne", ale snapshot trzyma stan:
    assert row.stany_pol_snapshot is not None
    assert row.stany_pol()["tytul"] == "zmienione"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_stany_pol.py::test_stany_pol_snapshot_stabilny_po_integracji -p no:randomly -q`
Expected: FAIL — `AttributeError: … 'stany_pol_snapshot'`.

- [ ] **Step 3: Dodaj pole na modelu**

W `models.py`, w klasie `ImportPracownikowRow` (obok innych pól, np. po `utworz_nowego`), dodaj:

```python
    # Snapshot stanów pól (POLA_ROZNIC) zamrożony przy integracji — po niej baza
    # = plik, więc live porównanie dałoby „zgodne"; filtr czyta stabilną wartość.
    stany_pol_snapshot = JSONField(null=True, blank=True)
```

(`JSONField` jest już zaimportowany — patrz `dane_znormalizowane`, `models.py:583`.)

- [ ] **Step 4: `stany_pol()` — preferuj snapshot**

Zmień metodę `stany_pol` z Task 2:

```python
    def stany_pol(self):
        """Stan każdego pola różnic: ``{klucz: "zmienione"|"zgodne"|"brak"}``.
        Zwraca zamrożony ``stany_pol_snapshot`` gdy istnieje (po integracji),
        inaczej live wyliczenie z ``POLA_ROZNIC``."""
        if self.stany_pol_snapshot is not None:
            return self.stany_pol_snapshot
        from import_pracownikow.roznice import POLA_ROZNIC

        return {klucz: ekstraktor(self) for klucz, _et, ekstraktor in POLA_ROZNIC}
```

- [ ] **Step 5: Zapis snapshotu w `integrate()`**

W `integrate()` (`models.py:982`) dodaj zapis snapshotu jako PIERWSZĄ linię (przed resetem `log_zmian` i mutacjami — wtedy `porownaj_z_baza`/`*_id` wciąż odzwierciedlają różnice):

```python
    @transaction.atomic
    def integrate(self):
        assert self.zmiany_potrzebne
        # Zamroź stan pól ZANIM zmienimy bazę (potem live = „zgodne").
        self.stany_pol_snapshot = self.stany_pol()
        self.log_zmian = {"autor": [], "autor_jednostka": []}
        self._integrate_autor()
        self._integrate_autor_jednostka()
        self.save()
```

- [ ] **Step 6: Migracja**

Run: `cd ~/Programowanie/bpp-tabela-dwuwierszowa && DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow`
Expected: utworzony `src/import_pracownikow/migrations/0024_*.py` (AddField `stany_pol_snapshot`). Jeśli nazwa inna niż `0024_stany_pol_snapshot`, zostaw wygenerowaną.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_stany_pol.py -p no:randomly -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/migrations/0024_*.py src/import_pracownikow/tests/test_stany_pol.py
git commit -m "feat(import): snapshot stany_pol_snapshot przy integracji (stabilny filtr po integracji)"
```

---

### Task 4: Partiale — `<tbody>` + dwa `<tr>` (karta) + `data-diff-*` + nowe komparatory

**Files:**
- Modify: `.../partials/_wiersz_preview.html`
- Modify: `.../partials/_wiersz_preview_kom.html`
- Test: `src/import_pracownikow/tests/test_views_wiersz.py`, `tests/test_views_preview_render.py`

**Interfaces:**
- Consumes: `row.stany_pol()` (Task 3), `row.porownaj_z_baza()` z `tytul`/`funkcja` (Task 1), istniejące `row.confidence`, `row.confidence_badge`, `_autor_dane.html`, `_porownanie_kom.html`.
- Produces: `<tbody id="wiersz-{pk}">` z dwoma `<tr>`; pierwszy `<tr>` ma `data-diff-<klucz>` dla każdego klucza z `stany_pol()`.

- [ ] **Step 1: `_wiersz_preview.html` — `<tr>` → `<tbody>`**

Zamień całą zawartość pliku na:

```django
{# Wrapper wiersza podglądu — <tbody> obejmujący DWA <tr> (karta rekordu). #}
{# Akcje HTMX swapują innerHTML tego <tbody> (→ _wiersz_preview_kom.html), #}
{# więc węzeł <tbody id="wiersz-{pk}"> zostaje stały, a filtr JS odczytuje #}
{# świeże data-diff-* z pierwszego <tr> po każdym swapie. #}
<tbody id="wiersz-{{ row.pk }}">
    {% include "import_pracownikow/partials/_wiersz_preview_kom.html" %}
</tbody>
```

- [ ] **Step 2: `_wiersz_preview_kom.html` — dwa `<tr>`**

Zamień całą zawartość pliku. Wiersz 1 (tożsamość + `data-diff-*`) i wiersz 2 (`colspan=5`, bloki). **Blok „Dopasowanie autora" i blok „Przepnij prace" to DOKŁADNIE istniejąca logika** (przenieś obecny kod: dawne komórki „Akcje/zmiany" i „Przepnij prace" — cały blok `{% if parent_object.edytowalny_podglad %}…{% endif %}` z autopickerem i `<script>` autopickera oraz blok przepięcia — bez zmian merytorycznych):

```django
{# Karta rekordu: <tr> nr 1 (tożsamość, read-only, data-diff-*) + <tr> nr 2 #}
{# (colspan=5: dopasowanie autora / komparatory plik→baza / przepnij prace). #}
<tr{% for klucz, stan in row.stany_pol.items %} data-diff-{{ klucz }}="{{ stan }}"{% endfor %}>
    <td class="import-poz">{{ row.nr_arkusza }}/{{ row.nr_wiersza }}</td>
    <td>
        <strong>{{ row.dane_znormalizowane.nazwisko }}</strong>
        {{ row.dane_znormalizowane.imię }}
        {% if row.dane_znormalizowane.tytuł_stopień %}
            <br>
            <span class="secondary">{{ row.dane_znormalizowane.tytuł_stopień }}</span>
        {% endif %}
    </td>
    <td>
        {% with badge=row.confidence_badge %}
            <span class="label {{ badge.0 }}">
                <i class="{{ badge.1 }}"></i> {{ badge.2 }}
            </span>
        {% endwith %}
    </td>
    <td>
        {% include "import_pracownikow/partials/_autor_dane.html" with autor=row.autor pbn_inst=row.autor_z_pbn_inst %}
    </td>
    <td>
        {% if row.jednostka %}
            {% if row.autor and row.autor.aktualna_jednostka_id and row.autor.aktualna_jednostka_id != row.jednostka_id %}
                {{ row.autor.aktualna_jednostka }} → <strong>{{ row.jednostka }}</strong>
            {% else %}
                {{ row.jednostka }}
            {% endif %}
        {% else %}
            <span class="secondary">— (jednostka odroczona / brak)</span>
        {% endif %}
    </td>
</tr>
<tr class="import-wiersz-szczegoly">
    <td colspan="5">
        <div class="import-szczegoly-bloki">
            <div class="import-blok import-blok-akcje">
                {# === PRZENIEŚ TU cały dawny blok „Akcje / zmiany": === #}
                {# {% if parent_object.edytowalny_podglad %} … pełna logika #}
                {# confidence (wielu/brak/twardy) + <script> autopickera … #}
                {# {% else %} {% for elem in row.sformatowany_log_zmian %} #}
                {# <p>{{ elem }}</p> {% endfor %} {% endif %} #}
            </div>
            <div class="import-blok import-blok-porownania">
                {% with porownanie=row.porownaj_z_baza %}
                    <div class="import-porownanie-item">
                        <span class="import-porownanie-etykieta">E-mail:</span>
                        {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.email ostrzezenie=row.ostrzezenie_email %}
                    </div>
                    <div class="import-porownanie-item">
                        <span class="import-porownanie-etykieta">Tytuł nauk.:</span>
                        {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.tytul %}
                    </div>
                    <div class="import-porownanie-item">
                        <span class="import-porownanie-etykieta">Stopień sł.:</span>
                        {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.stopien %}
                    </div>
                    <div class="import-porownanie-item">
                        <span class="import-porownanie-etykieta">Funkcja:</span>
                        {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.funkcja %}
                    </div>
                    <div class="import-porownanie-item">
                        <span class="import-porownanie-etykieta">Stanowisko dyd.:</span>
                        {% include "import_pracownikow/partials/_porownanie_kom.html" with pole=porownanie.stanowisko %}
                    </div>
                {% endwith %}
            </div>
            <div class="import-blok import-blok-przepnij">
                {# === PRZENIEŚ TU dawny blok „Przepnij prace": === #}
                {# {% if parent_object.edytowalny_podglad and row.przepnij_dostepne %} #}
                {# … form przepnij-prace … {% elif row.log_zmian.przepiecie %} #}
                {# … plakietka audytu … {% else %} — {% endif %} #}
            </div>
        </div>
    </td>
</tr>
```

> Wskazówka wykonawcza: skopiuj dawną zawartość dwóch ostatnich `<td>` z git-a
> (`git show HEAD:src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html`)
> i wklej BEZ ZMIAN w oznaczone miejsca (blok-akcje = dawna komórka „Akcje/zmiany"
> linie ~44–205; blok-przepnij = dawna komórka „Przepnij prace" linie ~206–233).
> `hx-target="#wiersz-{{row.pk}}"` / `hx-swap="innerHTML"` zostają — teraz celują w `<tbody>`.

- [ ] **Step 3: Run HTMX-swap + render tests**

Run: `uv run pytest src/import_pracownikow/tests/test_views_wiersz.py src/import_pracownikow/tests/test_views_preview_render.py -p no:randomly -q`
Expected: mogą wystąpić błędy asercji odwołujące się do starego układu — napraw je w Step 4. (Widok HTMX renderuje ten sam partial → zwraca teraz dwa `<tr>`.)

- [ ] **Step 4: Dostosuj testy do nowego markupu**

Dla każdej padającej asercji w tych plikach: zamień oczekiwanie na nowy układ (np. obecność `data-diff-tytul=` w odpowiedzi, obecność `colspan="5"`, treść komparatora). Zachowaj sens testu (swap pokazuje zaktualizowanego autora). Dodaj minimalny nowy asert:

```python
def test_wiersz_ma_atrybuty_data_diff(...):
    # w odpowiedzi HTMX-swapu pierwszy <tr> niesie stany pól
    assert 'data-diff-jednostka=' in resp.content.decode()
```

(Dopasuj fixture/wywołanie do wzorca już obecnego w `test_views_wiersz.py`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_views_wiersz.py src/import_pracownikow/tests/test_views_preview_render.py -p no:randomly -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview_kom.html src/import_pracownikow/tests/test_views_wiersz.py src/import_pracownikow/tests/test_views_preview_render.py
git commit -m "feat(import): dwuwierszowa karta rekordu (tbody+2×tr) z data-diff-* i komparatorami tytuł/funkcja"
```

---

### Task 5: Lista — nowy `<thead>`, usunięcie DataTables, pasek filtrów + JS

**Files:**
- Modify: `src/import_pracownikow/views.py` (`ImportPracownikowResultsView.get_context_data`, ~`views.py:625-660`)
- Modify: `.../templates/import_pracownikow/importpracownikowrow_list.html`
- Test: `src/import_pracownikow/tests/test_views_preview_render.py`

**Interfaces:**
- Consumes: `data-diff-*` na `<tbody>>tr` (Task 4), `POLA_ROZNIC` (Task 2).
- Produces: kontekst `pola_roznic = [(klucz, etykieta), …]`; pasek `<form id="filtr-roznic">`; funkcja JS filtrująca `#tabela-autorow > tbody`.

- [ ] **Step 1: Write the failing test**

Dopisz do `test_views_preview_render.py` (dopasuj helper renderujący widok do istniejącego w pliku, np. `_render(...)` / `client`):

```python
def test_pasek_filtrow_ma_radia_dla_pol(...):
    tresc = ...  # wyrenderowana strona rezultatów (jak w istniejących testach)
    assert 'id="filtr-roznic"' in tresc
    for klucz in ("jednostka", "email", "tytul", "stopien", "funkcja", "stanowisko"):
        assert f'name="filtr-{klucz}"' in tresc
    # 4 opcje radia dla pola
    assert 'value="zmienione"' in tresc
    assert 'value="brak"' in tresc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py -k filtrow -p no:randomly -q`
Expected: FAIL — `id="filtr-roznic"` brak.

- [ ] **Step 3: Widok — dołóż `pola_roznic` do kontekstu**

W `views.py`, w `ImportPracownikowResultsView.get_context_data`:

```python
        from import_pracownikow.roznice import POLA_ROZNIC

        ctx["pola_roznic"] = [(k, etykieta) for k, etykieta, _ in POLA_ROZNIC]
```

(Jeśli klasa nie ma jeszcze `get_context_data`, dodaj ją: pobierz `ctx = super().get_context_data(**kwargs)`, dołóż klucz, `return ctx`.)

- [ ] **Step 4: `importpracownikowrow_list.html` — nowy `<thead>` + pasek + JS**

W bloku `{% if parent_object.finished_successfully %}`:

(a) Zamień `<thead>…</thead>` (linie ~58-74) na 5 kolumn — zachowaj DOSŁOWNIE nagłówek „Jednostka (obecna → z pliku)":

```django
                <thead>
                    <tr>
                        <th>Poz</th>
                        <th>Osoba (z pliku)</th>
                        <th>Pewność</th>
                        <th>Autor (BPP)</th>
                        <th>Jednostka (obecna → z pliku)</th>
                    </tr>
                </thead>
```

(b) `{% empty %}` — colspan na 5, we własnym `<tbody>`:

```django
                    {% empty %}
                    <tbody>
                        <tr>
                            <td colspan="5" class="text-center"><strong>
                                Żadnych wierszy do pokazania.
                            </strong></td>
                        </tr>
                    </tbody>
```

(c) Nad `<div style="overflow-x: auto;">` (przed tabelą) wstaw pasek filtrów:

```django
        <form id="filtr-roznic" class="import-filtr-roznic">
            <label class="import-filtr-tekst">
                Szukaj:
                <input type="search" id="filtr-tekst" placeholder="nazwisko / jednostka…">
            </label>
            {% for klucz, etykieta in pola_roznic %}
                <fieldset class="import-filtr-pole">
                    <legend>{{ etykieta }}</legend>
                    <label><input type="radio" name="filtr-{{ klucz }}" value="wszystkie" checked> wszystkie</label>
                    <label><input type="radio" name="filtr-{{ klucz }}" value="zmienione"> zmienione</label>
                    <label><input type="radio" name="filtr-{{ klucz }}" value="zgodne"> zgodne</label>
                    <label><input type="radio" name="filtr-{{ klucz }}" value="brak"> brak w pliku</label>
                </fieldset>
            {% endfor %}
        </form>
```

(d) USUŃ blok `<script> $(function () { var dt = $('#tabela-autorow').DataTable(… )… htmx:afterSettle … dt.row(tr).invalidate … }); </script>` (linie ~90-113) i zastąp skryptem filtra:

```django
        <script>
        (function () {
            var form = document.getElementById('filtr-roznic');
            var tabela = document.getElementById('tabela-autorow');
            if (!form || !tabela) return;

            function klucze() {
                var s = new Set();
                form.querySelectorAll('input[type=radio]').forEach(function (r) {
                    s.add(r.name.replace(/^filtr-/, ''));
                });
                return Array.from(s);
            }
            function wybor(klucz) {
                var el = form.querySelector(
                    'input[name="filtr-' + klucz + '"]:checked');
                return el ? el.value : 'wszystkie';
            }
            function stanPola(tbody, klucz) {
                var tr = tbody.querySelector(':scope > tr[data-diff-' + klucz + ']');
                return tr ? tr.getAttribute('data-diff-' + klucz) : null;
            }
            function tekst() {
                var el = document.getElementById('filtr-tekst');
                return (el ? el.value : '').trim().toLowerCase();
            }
            function filtruj() {
                var ks = klucze();
                var q = tekst();
                tabela.querySelectorAll(':scope > tbody').forEach(function (tbody) {
                    var okStany = ks.every(function (klucz) {
                        var w = wybor(klucz);
                        return w === 'wszystkie' || stanPola(tbody, klucz) === w;
                    });
                    var okTekst = !q ||
                        tbody.textContent.toLowerCase().indexOf(q) !== -1;
                    tbody.hidden = !(okStany && okTekst);
                });
            }
            form.addEventListener('change', filtruj);
            form.addEventListener('input', filtruj);
            document.body.addEventListener('htmx:afterSettle', filtruj);
        })();
        </script>
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py src/import_pracownikow/tests/test_views_liveops.py -p no:randomly -q`
Expected: PASS (w tym stare asercje `id="tabela-autorow"`, „Lista modyfikacji", „Jednostka (obecna → z pliku)").

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html src/import_pracownikow/tests/test_views_preview_render.py
git commit -m "feat(import): pasek filtrów stanu pól + usunięcie DataTables (filtr client-side nad tbody)"
```

---

### Task 6: SCSS — karta rekordu + pasek filtrów

**Files:**
- Modify: `src/bpp/static/scss/_import-pracownikow.scss`

**Interfaces:**
- Consumes: klasy z Task 4/5 (`import-wiersz-szczegoly`, `import-szczegoly-bloki`, `import-blok`, `import-filtr-roznic`, `import-filtr-pole`, `import-poz`).

- [ ] **Step 1: Dopisz style**

Na końcu `_import-pracownikow.scss`:

```scss
// Tabela autorów jako dwuwierszowa „karta": rekord = <tbody> z dwoma <tr>.
#tabela-autorow {
  > tbody {
    border-top: 2px solid #cacaca; // rozdzielenie kart

    // wspólne tło obu wierszy rekordu; zebra po rekordach
    &:nth-of-type(odd) > tr {
      background-color: #f6f6f6;
    }

    // wiersz 2 sklejony z wierszem 1 (bez górnej ramki)
    > tr.import-wiersz-szczegoly > td {
      border-top: none;
      padding-top: 0;
    }
  }

  .import-poz {
    white-space: nowrap;
    color: #767676;
    font-size: 0.85em;
  }
}

// Bloki wiersza szczegółów — poziomo, zawijają się.
.import-szczegoly-bloki {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-start;

  .import-blok {
    min-width: 12rem;
    flex: 1 1 14rem;
  }
  .import-blok-akcje {
    flex: 2 1 22rem; // picker autora dostaje więcej miejsca
  }
}

.import-porownanie-item {
  margin-bottom: 0.25rem;
}
.import-porownanie-etykieta {
  font-weight: bold;
  margin-right: 0.25rem;
}

// Pasek filtrów „zmienione / zgodne / brak".
.import-filtr-roznic {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1rem;

  .import-filtr-pole {
    border: 1px solid #cacaca;
    border-radius: 3px;
    padding: 0.35rem 0.6rem;
    margin: 0;

    legend {
      font-size: 0.8em;
      font-weight: bold;
      padding: 0 0.3rem;
    }
    label {
      display: block;
      font-size: 0.85em;
      margin: 0;
    }
  }
  .import-filtr-tekst {
    align-self: center;
  }
}
```

- [ ] **Step 2: Zbuduj CSS**

Run: `cd ~/Programowanie/bpp-tabela-dwuwierszowa && grunt build`
Expected: kompilacja bez błędów SCSS; zmieniony `common.css` w `src/bpp/static`.

- [ ] **Step 3: Commit**

```bash
git add src/bpp/static/scss/_import-pracownikow.scss src/bpp/static/bpp/css/ src/bpp/static/**/common*.css
git commit -m "style(import): SCSS karty rekordu + paska filtrów"
```

(Uwaga: dodaj faktycznie zmienione artefakty CSS wskazane przez `git status` po `grunt build`.)

---

### Task 7: Newsfragment + pełny sweep testów + smoke

**Files:**
- Create: `src/bpp/newsfragments/import-tabela-dwuwierszowa.feature.rst`
- Verify: cały moduł + testy renderu

- [ ] **Step 1: Newsfragment**

Utwórz `src/bpp/newsfragments/import-tabela-dwuwierszowa.feature.rst`:

```rst
Tabela autorów w imporcie pracowników jest teraz dwuwierszową „kartą"
(mieści się w interfejsie, akcje mają miejsce), a nad nią pasek filtrów
pozwala pokazać osoby, u których dane pole (jednostka, e-mail, tytuł
naukowy, stopień służbowy, funkcja w jednostce, stanowisko dydaktyczne)
jest zmienione, zgodne albo puste w pliku. Doszły też kolumny „plik → baza"
dla tytułu naukowego i funkcji w jednostce oraz doprecyzowane etykiety pól
(„Tytuł / stopień naukowy", „Stopień służbowy (np. major, kapitan)").
```

- [ ] **Step 2: Cały moduł importu**

Run: `uv run pytest src/import_pracownikow/ -p no:randomly -q 2>&1 | tee /tmp/imp_tests.log; echo EXIT=${PIPESTATUS[0]}`
Expected: `EXIT=0`. Napraw ewentualne regresje asercji markupu (szukaj w logu odwołań do usuniętych kolumn/DataTables).

- [ ] **Step 3: Smoke wizualny (opcjonalny, jeśli dostępny run-site)**

Run: `uv run run-site run --no-browser --skip-assets` w tle; pobierz stronę rezultatów zalogowanym curl-em (patrz CLAUDE.md „Autologin"); potwierdź: pasek filtrów widoczny, karty dwuwierszowe, filtr radio zawęża wiersze.

- [ ] **Step 4: Commit**

```bash
git add src/bpp/newsfragments/import-tabela-dwuwierszowa.feature.rst
git commit -m "docs(import): newsfragment — karta rekordu + filtr stanu pól"
```

---

## Po zaimplementowaniu (poza taskami)

- **Baseline refresh** przy scalaniu do `dev` (nowa migracja 0024): `make baseline-update`, commit `baseline-sql/baseline.sql` + `baseline.meta.json`. NIE w trakcie równoległych branchy.
- Pełna suita: `make tests-without-playwright` (i całość `make tests` jeśli dotknięto ścieżek Playwright).
- PR do `dev`.

## Self-Review (wykonano)

- **Pokrycie spec:** Część A (karta) → Task 4/5/6; Część B (filtr, 6 pól, AND, 3 stany, nowe kolumny tytuł/funkcja, rejestr, snapshot, dostępność) → Task 1/2/3/4/5; niuans braku autora → Task 1+2. Etykiety pól (mapping) już w worktree.
- **Placeholdery:** brak „TODO"; jedyne „PRZENIEŚ TU" to jawne, oznaczone przeniesienie istniejącego bloku z podaniem źródła (`git show HEAD:…`, linie).
- **Spójność typów/nazw:** klucze pól (`jednostka,email,tytul,stopien,funkcja,stanowisko`) spójne między `POLA_ROZNIC`, `porownaj_z_baza` (`tytul`/`funkcja`), `data-diff-*`, `name="filtr-<klucz>"` i JS. `stany_pol()` sygnatura spójna Task 2↔3.
