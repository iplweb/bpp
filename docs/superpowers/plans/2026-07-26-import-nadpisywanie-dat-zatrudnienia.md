# Import: nadpisywanie dat zatrudnienia z pliku — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Opcja per-import „Nadpisuj daty zatrudnienia (od/do) wartościami
z pliku" — schowana w szufladzie formularza, z confirm-em przy zaznaczaniu
i ostrzeżeniem (callout + confirm) w końcowym formularzu zapisu osób.

**Architecture:** Flaga `BooleanField` na `ImportPracownikow`; bramka
`zmiany_potrzebne` i `_integruj_daty_aj` stają się flag-aware; pythonowy
pre-check nakładania okresów (lustro `ExclusionConstraint`) przed save;
licznik realnych nadpisań zasila ostrzeżenie finalizacji.

**Tech Stack:** Django 4.x, pytest + model_bakery, crispy-forms
(Foundation), szablony Django.

**Spec:** `docs/superpowers/specs/2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md`

## Global Constraints

- ZAWSZE `uv run` przed każdym poleceniem Pythona (`uv run pytest`, `uv run python src/manage.py ...`).
- Testy: pytest, funkcje bez klas, `@pytest.mark.django_db`, `model_bakery.baker.make`. NIGDY unittest.TestCase.
- Pytest z `-n auto` przy pełnych przebiegach; pojedyncze testy mogą iść bez.
- Wyjście testów ZAWSZE do pliku: `... 2>&1 | tee /tmp/wynik.log` — potem grep; nie uruchamiaj tego samego przebiegu dwa razy.
- Max 88 znaków linii (ruff). Po edycjach: `ruff format <pliki>` i `ruff check <pliki>` (tylko zmienione pliki, nigdy `--all-files`).
- Komentarze szablonów Django `{# ... #}` są JEDNOLINIOWE — każda linia z własnym `{#` i `#}`.
- Publiczny frontend = Foundation Icons (`<span class="fi-...">`), NIE emoji.
- NIE modyfikować istniejących (wydanych) migracji; nowa migracja = `0028`.
- Newsfragment: `src/bpp/newsfragments/<slug>.feature.rst`, po polsku.
- Baseline bazy NIE odświeżać na gałęzi — raz, przy scalaniu (`make baseline-update`).
- Praca na gałęzi `feat/import-nadpisywanie-dat` od `dev`; commity małe, po każdym tasku.
- Nazwy z specu (spójność międzytaskowa): pole modelu `nadpisuj_daty_zatrudnienia`; metoda wiersza `nadpisze_daty()`; metoda parenta `liczba_nadpisan_dat()`; metoda pre-checku `_sprawdz_nakladanie_okresow(aj)`.

---

### Task 0: Gałąź robocza

**Files:** brak zmian w plikach.

- [ ] **Step 1: Utwórz gałąź od dev**

```bash
cd /Users/mpasternak/Programowanie/bpp
git checkout dev && git pull --ff-only && git checkout -b feat/import-nadpisywanie-dat
```

---

### Task 1: Pole modelu + migracja 0028

**Files:**
- Modify: `src/import_pracownikow/models.py` (klasa `ImportPracownikow`, po polu `przepnij_wszystkie_prace`, ok. linii 171)
- Create: `src/import_pracownikow/migrations/0028_nadpisuj_daty_zatrudnienia.py` (generowana)
- Test: `src/import_pracownikow/tests/test_nadpisywanie_dat.py` (nowy plik)

**Interfaces:**
- Produces: `ImportPracownikow.nadpisuj_daty_zatrudnienia: bool` (default `False`) — czytane w Taskach 2-6.

- [ ] **Step 1: Napisz failujący test**

Utwórz `src/import_pracownikow/tests/test_nadpisywanie_dat.py`:

```python
"""Opcja „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku" —
flaga modelu, bramka zmian, nadpisywanie w integracji, pre-check
nakładania okresów, licznik ostrzeżenia finalizacji (spec
2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md)."""

import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_flaga_nadpisywania_domyslnie_wylaczona():
    parent = baker.make(ImportPracownikow)
    assert parent.nadpisuj_daty_zatrudnienia is False
```

- [ ] **Step 2: Uruchom test — ma paść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -x 2>&1 | tee /tmp/t1.log | tail -5
```

Oczekiwane: FAIL/ERROR (`AttributeError` / pole nie istnieje).

- [ ] **Step 3: Dodaj pole do modelu**

W `src/import_pracownikow/models.py`, w klasie `ImportPracownikow`,
bezpośrednio PO polu `przepnij_wszystkie_prace` (przed
`zakres_integracji`):

```python
    nadpisuj_daty_zatrudnienia = models.BooleanField(
        "Nadpisuj daty zatrudnienia (od/do) wartościami z pliku",
        default=False,
        # HTML w help_text (crispy renderuje przez |safe) — wzorzec jak w
        # przepnij_wszystkie_prace. Ten sam string dosłownie w migracji 0028.
        help_text="Gdy zaznaczone, daty rozpoczęcia i zakończenia pracy "
        "<strong>ISTNIEJĄCYCH</strong> okresów zatrudnienia zostaną "
        "<strong>NADPISANE</strong> wartościami z pliku — tam, gdzie plik "
        "niesie datę różną od bazy.<br>"
        "Użyj do KOREKTY dat (np. po wcześniejszym imporcie pliku bez "
        "dat, który ostemplował wszystkich datą importu).<br>"
        "Puste komórki pliku niczego nie kasują. Dotyczy wyłącznie osób "
        "obecnych w pliku.",
    )
```

- [ ] **Step 4: Wygeneruj migrację**

```bash
DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow -n nadpisuj_daty_zatrudnienia 2>&1 | tail -3
```

Oczekiwane: powstaje `src/import_pracownikow/migrations/0028_nadpisuj_daty_zatrudnienia.py`
(AddField). Obejrzyj plik — ma zawierać wyłącznie to jedno AddField.

- [ ] **Step 5: Uruchom test — ma przejść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -x 2>&1 | tee /tmp/t1b.log | tail -5
```

Oczekiwane: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/migrations/0028_nadpisuj_daty_zatrudnienia.py src/import_pracownikow/tests/test_nadpisywanie_dat.py
git commit -m "feat(import_pracownikow): pole nadpisuj_daty_zatrudnienia (mig 0028)"
```

---

### Task 2: Formularz (szuflada) + confirm przy zaznaczaniu

**Files:**
- Modify: `src/import_pracownikow/forms.py` (`NowyImportForm`, linie 16-70)
- Modify: `src/import_pracownikow/templates/import_pracownikow/importpracownikow_form.html` (blok `<script>`, linie 25-47)
- Test: `src/import_pracownikow/tests/test_nadpisywanie_dat.py`

**Interfaces:**
- Consumes: `ImportPracownikow.nadpisuj_daty_zatrudnienia` (Task 1).
- Produces: pole `nadpisuj_daty_zatrudnienia` w `NowyImportForm` (checkbox w `<details>`), confirm JS na `#id_nadpisuj_daty_zatrudnienia`.

- [ ] **Step 1: Napisz failujące testy**

Dopisz do `test_nadpisywanie_dat.py`:

```python
from import_pracownikow.forms import NowyImportForm


def test_formularz_ma_pole_nadpisywania_dat():
    form = NowyImportForm()
    assert "nadpisuj_daty_zatrudnienia" in form.fields
    assert form.fields["nadpisuj_daty_zatrudnienia"].initial in (None, False)


def test_formularz_pole_nadpisywania_w_szufladzie():
    # Pole ma być w zwiniętym <details> (szuflada opcji zaawansowanych).
    from crispy_forms.utils import render_crispy_form

    html = render_crispy_form(NowyImportForm())
    assert "<details" in html
    pozycja_details = html.index("<details")
    pozycja_pola = html.index("nadpisuj_daty_zatrudnienia")
    assert pozycja_pola > pozycja_details
```

- [ ] **Step 2: Uruchom testy — mają paść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -x 2>&1 | tee /tmp/t2.log | tail -5
```

Oczekiwane: FAIL (`KeyError: 'nadpisuj_daty_zatrudnienia'`).

- [ ] **Step 3: Dodaj pole do formularza**

W `src/import_pracownikow/forms.py`, w `NowyImportForm.Meta.fields` dopisz
`"nadpisuj_daty_zatrudnienia"`:

```python
        fields = [
            "plik_xls",
            "data_zmian_personalnych",
            "przepnij_wszystkie_prace",
            "nadpisuj_daty_zatrudnienia",
        ]
```

W layoutcie zmień nagłówek szuflady i dodaj Row (blok `HTML(...)` +
`Row(...)` between details, linie 49-57) — całość po zmianie:

```python
                # Opcje groźne i rzadko potrzebne — chowamy je w domyślnie
                # ZWINIĘTYM <details> (natywny collapsible, bez JS). Input
                # zwiniętego <details> normalnie się wysyła, a confirm-y (po
                # #id_...) dalej działają.
                HTML(
                    '<details class="callout secondary">'
                    '<summary><span class="fi-widget"></span> '
                    "Opcje zaawansowane</summary>"
                ),
                Row(
                    Column("przepnij_wszystkie_prace", css_class="large-12 small-12"),
                ),
                Row(
                    Column(
                        "nadpisuj_daty_zatrudnienia", css_class="large-12 small-12"
                    ),
                ),
                HTML("</details>"),
```

- [ ] **Step 4: Dodaj confirm JS w szablonie**

W `importpracownikow_form.html` w istniejącym `<script>` (po handlerze
`id_przepnij_wszystkie_prace`, przed zamknięciem `DOMContentLoaded`)
dopisz:

```javascript
        var cbDaty = document.getElementById('id_nadpisuj_daty_zatrudnienia');
        if (cbDaty) {
            cbDaty.addEventListener('change', function () {
                if (!cbDaty.checked) { return; }
                var ok = confirm(
                    "UWAGA — NADPISYWANIE DAT ZATRUDNIENIA\n\n" +
                    "Zaznaczasz opcję, która przy zapisie osób NADPISZE " +
                    "istniejące daty rozpoczęcia/zakończenia pracy " +
                    "wartościami z pliku (dla osób obecnych w pliku).\n\n" +
                    "Ręcznie ustawione daty w bazie zostaną UTRACONE tam, " +
                    "gdzie plik niesie inną datę.\n\n" +
                    "Użyj tylko, gdy plik jest źródłem prawdy o datach " +
                    "(np. korekta po imporcie bez dat).\n\n" +
                    "Czy na pewno wiesz, co robisz?"
                );
                if (!ok) { cbDaty.checked = false; }
            });
        }
```

Zaktualizuj też komentarz `{# ... #}` nad `<script>` (każda linia z
własnym `{#` i `#}`), np.:

```django
    {# Opcje z szuflady („przepnij wszystkie prace", „nadpisuj daty #}
    {# zatrudnienia") są groźne — przy ZAZNACZANIU wymuszamy świadome #}
    {# potwierdzenie (confirm). Anulowanie cofa zaznaczenie. Vanilla JS na #}
    {# DOMContentLoaded (nie zależy od kolejności $(document).ready). #}
```

- [ ] **Step 5: Uruchom testy — mają przejść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py src/import_pracownikow/tests/test_nowy_import_form.py 2>&1 | tee /tmp/t2b.log | tail -5
```

Oczekiwane: PASS (także istniejące testy formularza — nagłówek szuflady
się zmienił; jeśli któryś asertował stary tekst „masowe przepięcie prac",
zaktualizuj GO (asercję), nie formularz).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/forms.py src/import_pracownikow/templates/import_pracownikow/importpracownikow_form.html src/import_pracownikow/tests/
git commit -m "feat(import_pracownikow): checkbox nadpisywania dat w szufladzie + confirm"
```

---

### Task 3: Bramka `zmiany_potrzebne` świadoma flagi (§3.3a specu)

**Files:**
- Modify: `src/import_pracownikow/models.py` (`_check_autor_jednostka_needs_update`, linie 1249-1282)
- Test: `src/import_pracownikow/tests/test_nadpisywanie_dat.py`

**Interfaces:**
- Consumes: `self.parent.nadpisuj_daty_zatrudnienia` (Task 1), `self._plik_od()` / `self._plik_do()` (istniejące, `models.py:1020-1033`, zwracają `date | None`).
- Produces: `check_if_integration_needed()` zwraca `True` dla wiersza z samą różnicą dat przy fladze ON — na tym polegają analiza (`analyze.py:766`), pewnosc (`pewnosc.py:134-137`) i świeży re-check (`integrate.py:227`), które wołają tę metodę bez zmian.

- [ ] **Step 1: Napisz failujące testy**

Dopisz do `test_nadpisywanie_dat.py`:

```python
from datetime import date

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikowRow


def _row_z_data(parent, dane, autor, jednostka, aj):
    return baker.make(
        ImportPracownikowRow,
        parent=parent,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane=dane,
    )


def _scenariusz_tytulowy(nadpisuj):
    """Otwarty okres od 2026-07-19 (fallback z poprzedniego importu),
    plik niesie 2021-10-01. Jedyna różnica wiersza = data od."""
    parent = baker.make(
        ImportPracownikow, nadpisuj_daty_zatrudnienia=nadpisuj
    )
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
        zakonczyl_prace=None,
        podstawowe_miejsce_pracy=True,
    )
    row = _row_z_data(
        parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj
    )
    return row, aj


@pytest.mark.django_db
def test_bramka_roznica_dat_flaga_on():
    row, _ = _scenariusz_tytulowy(nadpisuj=True)
    assert row.check_if_integration_needed() is True


@pytest.mark.django_db
def test_bramka_roznica_dat_flaga_off_jak_dzis():
    row, _ = _scenariusz_tytulowy(nadpisuj=False)
    assert row.check_if_integration_needed() is False
```

- [ ] **Step 2: Uruchom testy — ON ma paść, OFF ma przejść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -x -k bramka 2>&1 | tee /tmp/t3.log | tail -8
```

Oczekiwane: `test_bramka_roznica_dat_flaga_on` FAIL (bramka nie zna
flagi), `..._off_jak_dzis` PASS.

- [ ] **Step 3: Rozszerz `_check_autor_jednostka_needs_update`**

W `src/import_pracownikow/models.py` przed listą `checks` dodaj
zmienne, a do listy dwa nowe warunki (na końcu listy):

```python
        # §3.3a specu nadpisywania dat: przy fladze „nadpisuj daty" różnica
        # wobec ISTNIEJĄCEJ (niepustej) daty też wymaga integracji — bez
        # flagi liczy się, jak dotąd, wyłącznie wypełnienie NULL-a.
        nadpisywanie = self.parent.nadpisuj_daty_zatrudnienia
        plik_od, plik_do = self._plik_od(), self._plik_do()
        checks = [
            ...(istniejące warunki bez zmian)...,
            nadpisywanie
            and plik_od is not None
            and aj.rozpoczal_prace is not None
            and aj.rozpoczal_prace != plik_od,
            nadpisywanie
            and plik_do is not None
            and aj.zakonczyl_prace is not None
            and aj.zakonczyl_prace != plik_do,
        ]
```

(`...(istniejące warunki bez zmian)...` = pozostaw 8 obecnych pozycji
listy dokładnie jak są — dopisz DWIE nowe na końcu.)

- [ ] **Step 4: Uruchom testy — mają przejść (plus regresja bramki)**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py src/import_pracownikow/tests/test_pewnosc.py src/import_pracownikow/tests/test_okresy_resolver.py 2>&1 | tee /tmp/t3b.log | tail -5
```

Oczekiwane: PASS wszystkie.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_nadpisywanie_dat.py
git commit -m "feat(import_pracownikow): bramka zmiany_potrzebne swiadoma flagi nadpisywania dat"
```

---

### Task 4: Nadpisywanie w `_integruj_daty_aj` + log zmian

**Files:**
- Modify: `src/import_pracownikow/models.py` (`_integruj_daty_aj`, linie 1333-1357; wywołanie w `_integrate_autor_jednostka`, linia 1368)
- Test: `src/import_pracownikow/tests/test_nadpisywanie_dat.py`

**Interfaces:**
- Consumes: `self.parent.nadpisuj_daty_zatrudnienia`, `dane` = `dane_bardziej_znormalizowane` (daty już jako `date`, `models.py:902-912`).
- Produces: `_integruj_daty_aj(aj, dane) -> bool` — `True` TYLKO gdy nadpisano niepustą wartość (sygnał dla pre-checku w Task 5; wypełnienia NULL-i → `False`).

- [ ] **Step 1: Napisz failujące testy**

Dopisz do `test_nadpisywanie_dat.py`:

```python
@pytest.mark.django_db
def test_integracja_nadpisuje_date_od_flaga_on():
    row, aj = _scenariusz_tytulowy(nadpisuj=True)
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2021, 10, 1)
    assert any(
        "nadpisano z pliku" in wpis
        for wpis in row.log_zmian["autor_jednostka"]
    )


@pytest.mark.django_db
def test_integracja_nie_nadpisuje_flaga_off():
    row, aj = _scenariusz_tytulowy(nadpisuj=False)
    # OFF: bramka nie przepuści wiersza; wołamy integrate() wprost, żeby
    # potwierdzić, że nawet wtedy data NIE jest ruszana.
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2026, 7, 19)


@pytest.mark.django_db
def test_integracja_nadpisuje_date_do():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=date(2026, 12, 31),
    )
    row = _row_z_data(
        parent,
        {"data_zatrudnienia": "2020-01-01", "data_końca_zatrudnienia": "2024-06-30"},
        autor,
        jednostka,
        aj,
    )
    row.integrate()
    aj.refresh_from_db()
    assert aj.zakonczyl_prace == date(2024, 6, 30)


@pytest.mark.django_db
def test_pusta_komorka_nie_kasuje_daty_przy_on():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=date(2024, 6, 30),
    )
    row = _row_z_data(parent, {}, autor, jednostka, aj)
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2020, 1, 1)
    assert aj.zakonczyl_prace == date(2024, 6, 30)
```

Uwaga wykonawcza: jeśli `row.integrate()` wymaga w tych testach
dodatkowych pól wiersza (np. słowników z `dane_znormalizowane`), wzoruj
się na istniejących testach integracji
(`src/import_pracownikow/tests/test_integrate_slowniki.py`) — dane
minimalne, `baker.make`.

- [ ] **Step 2: Uruchom testy — nadpisywanie ma paść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -x -k integracja 2>&1 | tee /tmp/t4.log | tail -8
```

Oczekiwane: `test_integracja_nadpisuje_date_od_flaga_on` i
`test_integracja_nadpisuje_date_do` FAIL (data niezmieniona); pozostałe
PASS.

- [ ] **Step 3: Przebuduj `_integruj_daty_aj`**

Zastąp ciało metody (docstring zaktualizuj — dopisz zwrot i gałąź
nadpisywania, zostaw opis zachowania bez flagi):

```python
    def _integruj_daty_aj(self, aj, dane):
        """Ustawia daty zatrudnienia na powiązaniu z danych wiersza.

        Bez flagi „nadpisuj daty": „data od"/„data do" na ISTNIEJĄCYM AJ
        wypełniamy TYLKO gdy baza ma ``NULL`` a plik NIESIE datę (§3:
        „wypełnienie NULL") — istniejącej daty nie ruszamy; pusty plik →
        nic nie zmieniaj (§5). Fallback ``data zmian → dziś`` dla NOWEGO
        okresu stempluje materializacja (``integrate._materializuj_diff``).

        Z flagą ``parent.nadpisuj_daty_zatrudnienia`` (spec §3.3): datę
        różną od niepustej wartości w bazie NADPISUJEMY wartością z pliku
        (osobno „od" i „do"); puste komórki nadal niczego nie kasują.

        Zwraca ``True`` TYLKO gdy nadpisano niepustą wartość — sygnał dla
        pre-checku nakładania okresów; wypełnienia NULL-i zwracają
        ``False`` (idą dzisiejszą ścieżką, bez pre-checku)."""
        nadpisywanie = self.parent.nadpisuj_daty_zatrudnienia
        nadpisano = False

        plik_od = dane.get("data_zatrudnienia")
        if plik_od:
            if aj.rozpoczal_prace is None:
                aj.rozpoczal_prace = plik_od
                self.log_zmian["autor_jednostka"].append(
                    f"data rozpoczęcia pracy na {aj.rozpoczal_prace}"
                )
            elif nadpisywanie and aj.rozpoczal_prace != plik_od:
                self.log_zmian["autor_jednostka"].append(
                    f"data rozpoczęcia pracy: {aj.rozpoczal_prace} → "
                    f"{plik_od} (nadpisano z pliku)"
                )
                aj.rozpoczal_prace = plik_od
                nadpisano = True

        data_konca = dane.get("data_końca_zatrudnienia")
        if data_konca:
            if aj.zakonczyl_prace is None:
                aj.zakonczyl_prace = data_konca
                self.log_zmian["autor_jednostka"].append(
                    f"data końca zatrudnienia na {data_konca}"
                )
            elif nadpisywanie and aj.zakonczyl_prace != data_konca:
                self.log_zmian["autor_jednostka"].append(
                    f"data końca zatrudnienia: {aj.zakonczyl_prace} → "
                    f"{data_konca} (nadpisano z pliku)"
                )
                aj.zakonczyl_prace = data_konca
                nadpisano = True

        return nadpisano
```

W `_integrate_autor_jednostka` (linia 1368) zmień wywołanie:

```python
        nadpisano_daty = self._integruj_daty_aj(aj, dane)
```

(`nadpisano_daty` zostanie użyte w Task 5 — na razie przypisanie
wystarczy; NIE dodawaj `noqa`, zmienna będzie użyta w następnym commicie
— jeśli ruff F841 blokuje commit, dodaj pre-check z Task 5 w tym samym
commicie.)

- [ ] **Step 4: Uruchom testy — mają przejść (plus regresja dat)**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py src/import_pracownikow/tests/test_porownywarka_daty.py src/import_pracownikow/tests/test_pipeline 2>&1 | tee /tmp/t4b.log | tail -5
```

Oczekiwane: PASS wszystkie.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_nadpisywanie_dat.py
git commit -m "feat(import_pracownikow): nadpisywanie dat AJ wartosciami z pliku (flaga ON)"
```

---

### Task 5: Pre-check nakładania okresów (lustro ExclusionConstraint)

**Files:**
- Modify: `src/import_pracownikow/models.py` (`_integrate_autor_jednostka`, ok. linii 1368-1388; nowa metoda `_sprawdz_nakladanie_okresow` obok)
- Test: `src/import_pracownikow/tests/test_nadpisywanie_dat.py`

**Interfaces:**
- Consumes: `nadpisano_daty: bool` z `_integruj_daty_aj` (Task 4), `BPPDatabaseError` (istniejący, używany w `models.py:1383`).
- Produces: `_sprawdz_nakladanie_okresow(aj)` — raise `BPPDatabaseError` przy kolizji; wołane TYLKO gdy `nadpisano_daty`.

- [ ] **Step 1: Napisz failujące testy**

Dopisz do `test_nadpisywanie_dat.py`:

```python
from import_common.exceptions import BPPDatabaseError


@pytest.mark.django_db
def test_nadpisanie_kolidujace_z_zamknietym_okresem_izolowane():
    # Zamknięty okres 2019-2022 + otwarty od 2026. Plik cofa otwarty na
    # 2021 → przedziały [2021,∞) i [2019-…-2022] nakładają się → błąd
    # izolowany PRZED save (constraint w bazie zatrułby transakcję).
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2019, 1, 1),
        zakonczyl_prace=date(2022, 12, 31),
    )
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
        zakonczyl_prace=None,
    )
    row = _row_z_data(
        parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj
    )
    with pytest.raises(BPPDatabaseError) as exc:
        row.integrate()
    assert "nakładają się" in str(exc.value)
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2026, 7, 19)  # nic nie zapisano


@pytest.mark.django_db
def test_wypelnienie_null_nie_odpala_precheku():
    # Wypełnienie NULL-a to dzisiejsza ścieżka — bez pre-checku, nawet
    # przy fladze ON (spec §3.4).
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=None,
        zakonczyl_prace=None,
    )
    row = _row_z_data(
        parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj
    )
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2021, 10, 1)


@pytest.mark.django_db
def test_od_wieksze_rowne_do_po_nadpisaniu_odrzucone():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=date(2021, 1, 1),
    )
    row = _row_z_data(
        parent, {"data_zatrudnienia": "2022-01-01"}, autor, jednostka, aj
    )
    with pytest.raises(BPPDatabaseError):
        row.integrate()
```

(`BPPDatabaseError` jest zdefiniowany w
`src/import_common/exceptions.py:90` — models.py importuje go z
`import_common.exceptions`, linia 23.)

- [ ] **Step 2: Uruchom testy — kolizja ma paść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -x -k "kolidujace or precheku or odrzucone" 2>&1 | tee /tmp/t5.log | tail -8
```

Oczekiwane: `test_nadpisanie_kolidujace...` FAIL (IntegrityError zamiast
BPPDatabaseError albo brak wyjątku), pozostałe dwa PASS.

- [ ] **Step 3: Dodaj pre-check**

W `src/import_pracownikow/models.py`, nowa metoda bezpośrednio POD
`_integruj_daty_aj`:

```python
    def _sprawdz_nakladanie_okresow(self, aj):
        """Pythonowe lustro constraintu
        ``bpp_autor_jednostka_okresy_bez_nakladan`` (bpp/models/autor.py):
        przedziały DOMKNIĘTE ``[od, do]``, ``zakonczyl_prace IS NULL`` =
        otwarty w prawo ``[od, ∞)``. Wołane TYLKO po nadpisaniu niepustej
        daty (flaga „nadpisuj daty") — naruszenie constraintu w bazie
        zatruwa transakcję i psuje izolację wiersza, więc kolizję łapiemy
        PRZED save (jak niezmiennik od<do wyżej)."""
        from bpp.models import Autor_Jednostka

        if aj.rozpoczal_prace is None:
            return
        od = aj.rozpoczal_prace
        do = aj.zakonczyl_prace or date.max
        koliduje = (
            Autor_Jednostka.objects.filter(
                autor_id=aj.autor_id,
                jednostka_id=aj.jednostka_id,
                rozpoczal_prace__isnull=False,
            )
            .exclude(pk=aj.pk)
            .filter(rozpoczal_prace__lte=do)
        )
        for inny in koliduje:
            if od <= (inny.zakonczyl_prace or date.max):
                raise BPPDatabaseError(
                    self.dane_z_xls,
                    self,
                    f"nadpisane daty ({od} – "
                    f"{aj.zakonczyl_prace or 'obecnie'}) nakładają się na "
                    f"inny okres zatrudnienia w tej jednostce "
                    f"({inny.rozpoczal_prace} – "
                    f"{inny.zakonczyl_prace or 'obecnie'})",
                )
```

W `_integrate_autor_jednostka`, PO istniejącym checku `od >= do`
(za linią `raise BPPDatabaseError(... jest późniejsza ...)`, przed
blokiem `funkcja_autora`):

```python
        if nadpisano_daty:
            self._sprawdz_nakladanie_okresow(aj)
```

- [ ] **Step 4: Uruchom testy — mają przejść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py 2>&1 | tee /tmp/t5b.log | tail -5
```

Oczekiwane: PASS wszystkie.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_nadpisywanie_dat.py
git commit -m "feat(import_pracownikow): pre-check nakladania okresow przed nadpisaniem dat"
```

---

### Task 6: Licznik nadpisań + callout + confirm w końcowym formularzu

**Files:**
- Modify: `src/import_pracownikow/models.py` (nowa metoda `ImportPracownikowRow.nadpisze_daty()`; nowa metoda `ImportPracownikow.liczba_nadpisan_dat()`)
- Modify: `src/import_pracownikow/views.py` (`PodgladImportuView.get_context_data`, linie 978-1039)
- Create: `src/import_pracownikow/templates/import_pracownikow/partials/_ostrzezenie_nadpisanie_dat.html`
- Modify: `src/import_pracownikow/templates/import_pracownikow/przeglad.html` (linie 194-216)
- Test: `src/import_pracownikow/tests/test_nadpisywanie_dat.py`

**Interfaces:**
- Consumes: `rozwiaz_okres_zatrudnienia` + `wstepnie_zaladuj_okresy` (`okresy.py`), `row._aj_lista()` (istniejące memo), wiersze parenta przez DOMYŚLNY related_name `importpracownikowrow_set` (FK `parent` nie ustawia własnego — `models.py:782-785`; tak samo robi reszta modelu, np. `models.py:400`).
- Produces: `ImportPracownikow.liczba_nadpisan_dat() -> int`; kontekst `nadpisywanie_dat_wlaczone: bool` i `liczba_nadpisan_dat: int` w `przeglad.html`.

- [ ] **Step 1: Napisz failujące testy**

Dopisz do `test_nadpisywanie_dat.py`:

```python
@pytest.mark.django_db
def test_liczba_nadpisan_dat_liczy_tylko_realne_nadpisania():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor1, autor2, autor3 = baker.make(Autor), baker.make(Autor), baker.make(Autor)
    jednostka = baker.make(Jednostka)
    # 1) realne nadpisanie: baza 2026, plik 2021 → LICZY SIĘ
    aj1 = baker.make(
        Autor_Jednostka, autor=autor1, jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor1, jednostka, aj1)
    # 2) wypełnienie NULL-a → NIE liczy się
    aj2 = baker.make(
        Autor_Jednostka, autor=autor2, jednostka=jednostka, rozpoczal_prace=None
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor2, jednostka, aj2)
    # 3) zgodne daty → NIE liczy się
    aj3 = baker.make(
        Autor_Jednostka, autor=autor3, jednostka=jednostka,
        rozpoczal_prace=date(2021, 10, 1),
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor3, jednostka, aj3)
    assert parent.liczba_nadpisan_dat() == 1


@pytest.mark.django_db
def test_liczba_nadpisan_dat_zero_przy_fladze_off():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=False)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    assert parent.liczba_nadpisan_dat() == 0
```

- [ ] **Step 2: Uruchom testy — mają paść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -x -k liczba 2>&1 | tee /tmp/t6.log | tail -5
```

Oczekiwane: FAIL (`AttributeError: liczba_nadpisan_dat`).

- [ ] **Step 3: Dodaj metody modelu**

`ImportPracownikowRow` (obok `_plik_od`/`_plik_do`):

```python
    def nadpisze_daty(self):
        """Czy zapis osób NADPISZE niepustą datę tego wiersza (flaga
        ``nadpisuj_daty_zatrudnienia``). Liczy TYLKO realne nadpisania —
        obie strony niepuste i różne; wypełnienia NULL-i i nowe okresy to
        NIE nadpisania (spec §3.5, stan „zmienione" ze ``stany_pol`` byłby
        zawyżony). Zasila licznik ostrzeżenia finalizacji."""
        if not self.parent.nadpisuj_daty_zatrudnienia:
            return False
        if self.autor_id is None or self.jednostka_id is None:
            return False
        from import_pracownikow.okresy import rozwiaz_okres_zatrudnienia

        rodzaj, aj = rozwiaz_okres_zatrudnienia(
            self.autor, self.jednostka, self._plik_od(), aj_lista=self._aj_lista()
        )
        if rodzaj != "istniejacy":
            return False
        plik_od, plik_do = self._plik_od(), self._plik_do()
        return bool(
            plik_od and aj.rozpoczal_prace and aj.rozpoczal_prace != plik_od
        ) or bool(
            plik_do and aj.zakonczyl_prace and aj.zakonczyl_prace != plik_do
        )
```

`ImportPracownikow` (obok `liczba_wierszy_do_pominiecia` — znajdź przez
grep):

```python
    def liczba_nadpisan_dat(self):
        """Ile wierszy przy zapisie osób NADPISZE istniejącą datę
        zatrudnienia (flaga ``nadpisuj_daty_zatrudnienia``) — do calloutu
        i confirmu finalizacji. Liczone LIVE (``stany_pol_snapshot`` bywa
        NULL do backfillu i miesza wypełnienia NULL-i z nadpisaniami);
        ``wstepnie_zaladuj_okresy`` + przypięcie ``parent`` chronią przed
        N+1."""
        if not self.nadpisuj_daty_zatrudnienia:
            return 0
        from import_pracownikow.okresy import wstepnie_zaladuj_okresy

        rows = list(
            self.importpracownikowrow_set.filter(
                autor__isnull=False, jednostka__isnull=False
            ).select_related("autor", "jednostka")
        )
        for row in rows:
            row.parent = self
        wstepnie_zaladuj_okresy(rows)
        return sum(1 for row in rows if row.nadpisze_daty())
```

- [ ] **Step 4: Uruchom testy metod — mają przejść**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py -k liczba 2>&1 | tee /tmp/t6b.log | tail -5
```

- [ ] **Step 5: Kontekst widoku + testy renderu**

W `PodgladImportuView.get_context_data` do `ctx.update({...})` dopisz:

```python
                # Ostrzeżenie finalizacji (spec nadpisywania dat §3.5):
                # licznik liczony tylko w fazie osób — w Kroku 1 formularz
                # zapisu osób i tak się nie renderuje.
                "nadpisywanie_dat_wlaczone": parent.nadpisuj_daty_zatrudnienia,
                "liczba_nadpisan_dat": (
                    parent.liczba_nadpisan_dat() if parent.faza_osob else 0
                ),
```

Dopisz testy renderu do `test_nadpisywanie_dat.py` — wzoruj klienta i
setup na istniejącym `src/import_pracownikow/tests/test_przeglad.py`
(fixture zalogowanego usera w grupie wprowadzania danych + parent w
stanie fazy osób; skopiuj stamtąd konstrukcję, nie wymyślaj własnej):

```python
def test_przeglad_callout_nadpisywania_widoczny_przy_on(...):
    # parent: stan fazy osób, nadpisuj_daty_zatrudnienia=True + 1 wiersz
    # z realnym nadpisaniem (jak w test_liczba_nadpisan_dat...).
    # GET przeglądu:
    # assert "Włączono nadpisywanie dat zatrudnienia" in html
    # assert "NADPISANE" in confirm-owym onsubmit formularza zapisu osób
    ...


def test_przeglad_bez_calloutu_przy_off(...):
    # identyczny setup, flaga OFF:
    # assert "Włączono nadpisywanie dat zatrudnienia" not in html
    ...
```

(Ciała testów uzupełnij konkretami z `test_przeglad.py` — asercje jak w
komentarzach powyżej; to jedyne dopuszczalne odstępstwo od gotowego kodu
w tym planie, bo fixtures przeglądu są rozbudowane i już istnieją.)

- [ ] **Step 6: Partial + przeglad.html**

Utwórz `src/import_pracownikow/templates/import_pracownikow/partials/_ostrzezenie_nadpisanie_dat.html`:

```django
{# Ostrzeżenie finalizacji: flaga „nadpisuj daty zatrudnienia" — zapis #}
{# osób NADPISZE istniejące daty wartościami z pliku (spec nadpisywania #}
{# dat §3.5). Liczba = realne nadpisania (obie strony niepuste i różne). #}
<div class="callout alert">
    <p>
        <span class="fi-alert"></span>
        <strong>Włączono nadpisywanie dat zatrudnienia.</strong>
        Wiersze z datami różnymi od bazy:
        <strong>{{ liczba_nadpisan_dat }}</strong> — ich daty rozpoczęcia
        / zakończenia pracy zostaną <strong>NADPISANE</strong>
        wartościami z pliku. Ręcznie ustawione daty zostaną utracone.
    </p>
</div>
```

W `przeglad.html`:

1. Po linii `{% include ".../_ostrzezenie_podstawowe_miejsce.html" %}`
   (linia 196) dodaj:

```django
                    {% if nadpisywanie_dat_wlaczone %}
                        {% include "import_pracownikow/partials/_ostrzezenie_nadpisanie_dat.html" %}
                    {% endif %}
```

2. Zmień `onsubmit` formularza (linia 205) tak, by obejmował oba
   ostrzeżenia (jedna linia — szablonowe `{% if %}` w atrybucie):

```django
                              {% if liczba_pominietych or liczba_nadpisan_dat %}onsubmit="return confirm('{% if liczba_pominietych %}Wiersze bez dopasowania zostaną pominięte: {{ liczba_pominietych }}. {% endif %}{% if liczba_nadpisan_dat %}Daty zatrudnienia zostaną NADPISANE wartościami z pliku dla wierszy: {{ liczba_nadpisan_dat }}. {% endif %}Kontynuować zapis?');"{% endif %}>
```

- [ ] **Step 7: Uruchom testy renderu + regresję przeglądu**

```bash
uv run pytest src/import_pracownikow/tests/test_nadpisywanie_dat.py src/import_pracownikow/tests/test_przeglad.py 2>&1 | tee /tmp/t6c.log | tail -5
```

Oczekiwane: PASS wszystkie.

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/views.py src/import_pracownikow/templates/ src/import_pracownikow/tests/
git commit -m "feat(import_pracownikow): ostrzezenie finalizacji o nadpisaniu dat (callout + confirm)"
```

---

### Task 7: Newsfragment + dokumentacja administratora

**Files:**
- Create: `src/bpp/newsfragments/nadpisywanie-dat-zatrudnienia.feature.rst`
- Modify: `docs/administrator/import-pracownikow.md`

- [ ] **Step 1: Newsfragment**

Utwórz `src/bpp/newsfragments/nadpisywanie-dat-zatrudnienia.feature.rst`:

```rst
Import pracowników: nowa opcja „Nadpisuj daty zatrudnienia (od/do)
wartościami z pliku" (szuflada „Opcje zaawansowane"). Pozwala skorygować
daty istniejących okresów zatrudnienia — np. po wcześniejszym imporcie
pliku bez dat, który ostemplował wszystkich datą importu. Puste komórki
niczego nie kasują; przed zapisem system pokazuje liczbę nadpisań i prosi
o potwierdzenie.
```

- [ ] **Step 2: Dokumentacja**

W `docs/administrator/import-pracownikow.md` znajdź sekcję o opcjach
formularza nowego importu (grep „przepnij" lub „Opcje"); dopisz PO niej
podsekcję:

```markdown
### Nadpisywanie dat zatrudnienia wartościami z pliku

Domyślnie import **nigdy nie nadpisuje** istniejących dat zatrudnienia —
wypełnia tylko puste („data od"/„data do" bez wartości w bazie), a
różnice pokazuje wyłącznie w podglądzie. Jeśli daty w bazie są błędne
(np. poprzedni import pliku bez dat ostemplował wszystkich datą importu),
zaznacz w szufladzie „Opcje zaawansowane" opcję **Nadpisuj daty
zatrudnienia (od/do) wartościami z pliku**:

- nadpisywane są tylko daty osób obecnych w pliku, tam gdzie plik niesie
  datę różną od bazy;
- puste komórki pliku niczego nie kasują;
- przy zaznaczaniu opcji oraz przed końcowym zapisem system prosi o
  potwierdzenie i pokazuje liczbę wierszy, których daty zostaną
  nadpisane;
- nadpisanie, które spowodowałoby nałożenie się dwóch okresów
  zatrudnienia w tej samej jednostce, jest odrzucane per-wiersz z
  czytelnym błędem.
```

(Dopasuj poziom nagłówka do konwencji pliku.)

- [ ] **Step 3: Commit**

```bash
git add src/bpp/newsfragments/nadpisywanie-dat-zatrudnienia.feature.rst docs/administrator/import-pracownikow.md
git commit -m "docs(import_pracownikow): newsfragment + dokumentacja nadpisywania dat"
```

---

### Task 8: Jakość, pełne testy modułu, PR

**Files:** bez nowych; poprawki z ruff/testów.

- [ ] **Step 1: Ruff na zmienionych plikach**

```bash
ruff format src/import_pracownikow/ src/bpp/newsfragments/ && ruff check src/import_pracownikow/
```

Oczekiwane: brak błędów (poprawki ręcznie, pojedynczo — nie `--fix`).

- [ ] **Step 2: Pełny przebieg testów modułu importu**

```bash
uv run pytest src/import_pracownikow/ -n auto 2>&1 | tee /tmp/import_all.log | tail -10
```

Oczekiwane: wszystkie PASS. Padnięte — napraw przed pushem (pamiętaj:
17 testów `api_v1 test_autor` bywało RED na dev niezależnie od nas — to
inny moduł; w `src/import_pracownikow/` ma być zielono).

- [ ] **Step 3: Push + PR do dev**

```bash
git push -u origin feat/import-nadpisywanie-dat
```

PR przez `gh api` (gh pr create flakuje):

```bash
gh api repos/{owner}/{repo}/pulls -f title="feat(import_pracownikow): nadpisywanie dat zatrudnienia wartościami z pliku" -f head=feat/import-nadpisywanie-dat -f base=dev -f body="$(cat <<'EOF'
Opcja per-import „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku"
(szuflada + confirm + ostrzeżenie finalizacji). Spec:
docs/superpowers/specs/2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md

- pole nadpisuj_daty_zatrudnienia (mig 0028) + checkbox w szufladzie z confirm-em
- bramka zmiany_potrzebne świadoma flagi (bez tego wiersz z samą różnicą dat nie wchodził do integracji)
- _integruj_daty_aj: nadpisywanie niepustych dat przy fladze ON, puste komórki nic nie kasują
- pythonowy pre-check nakładania okresów (lustro ExclusionConstraint) przed save
- callout + rozszerzony confirm w końcowym formularzu zapisu osób (licznik realnych nadpisań)

UWAGA przy scalaniu: migracja 0028 → `make baseline-update` (raz, przy merge).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Czekaj na REALNE gejty CI**

`Build test-runner image` + `Tests (sharded)` (wszystkie shardy) muszą
być zielone; równolegle można odpalić lokalnie
`make tests-without-playwright` (wynik do `/tmp/tests_local.log`).

---

## Self-review planu

- Pokrycie specu: §3.1→Task 1, §3.2→Task 2, §3.3→Task 4, §3.3a→Task 3,
  §3.4→Task 5, §3.5→Task 6, §3.6→testy w Taskach 1-6, §3.7→Task 7. ✓
- Typy/nazwy spójne między taskami (`nadpisuj_daty_zatrudnienia`,
  `nadpisze_daty()`, `liczba_nadpisan_dat()`,
  `_sprawdz_nakladanie_okresow(aj)`, zwrot bool z `_integruj_daty_aj`). ✓
- Jedyny niedosłowny fragment: ciała 2 testów renderu w Task 6 Step 5
  (fixtures kopiowane z istniejącego `test_przeglad.py` — wskazane
  źródło). Import `BPPDatabaseError` i related_name zweryfikowane w
  kodzie. ✓
