# Import pracowników — Faza 0 (liveops + dry-run/commit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przenieść `import_pracownikow` z frameworka `long_running` na `django-liveops`
oraz rozdzielić przetwarzanie na dry-run (analiza, nic nie pisze do `Autor`/
`Autor_Jednostka`) i osobny, jawny commit (integracja) — zachowując dotychczasową,
sztywną walidację kolumn (`AutorForm`/`JednostkaForm`).

**Architecture:** Model `ImportPracownikow` dziedziczy po `liveops.LiveOperation`.
Dodane pole aplikacyjne `stan` (maszyna: `utworzony → przeanalizowany → zatwierdzony
→ zintegrowany`, plus `porzucony`) steruje dyspozytorem `run(self, p)`: `utworzony`
→ analiza (tylko zapis `ImportPracownikowRow`, zero zapisów do domeny), `zatwierdzony`
→ integracja (materializuje odroczone `create()` + `row.integrate()`). Commit to
osobny widok `ZatwierdzImportView(RestartView)` ustawiający `stan="zatwierdzony"` przed
`super().post()`. Dry-run osiągamy odraczając wszystkie `create()` (słowniki
Funkcja/Grupa/Wymiar + `Autor_Jednostka`) do fazy integracji — analiza zapisuje je jako
`diff_do_utworzenia` (JSON) na wierszu, a FK zostają `null`.

**Tech Stack:** Django, `django-liveops` 0.3.0, pytest + `model_bakery`,
`liveops.testing.MockProgress`, openpyxl (bez zmian), PostgreSQL.

## Global Constraints

- Python: `uv run` prefix dla WSZYSTKICH poleceń Python (`uv run pytest`,
  `uv run python src/manage.py ...`). Nigdy gołe `python`.
- Max długość linii: 88 znaków (ruff).
- NIE modyfikować istniejących migracji w `src/*/migrations/`. Tylko nowe.
- Testy: pytest, funkcje bez klas, `@pytest.mark.django_db`, `baker.make`.
- Po zmianie schematu bazy: `make baseline-update` (delta).
- `long_running` API do usunięcia: `Operation`, `ASGINotificationMixin`, `perform`,
  `integrate` (auto), `on_reset`, `on_finished`, `send_progress`,
  `send_processing_finished`, pola `performed`/`integrated`.
- Grupa uprawnień widoków: `braces.GroupRequiredMixin`, `group_required =
  "wprowadzanie danych"`.
- `LIVEOPS["RUNNER"]` = `celery` (prod), `eager` (testy, `settings/test.py`).
- Namespace liveops zamontowany w `src/django_bpp/urls.py:274`
  (`path("live/", include("liveops.urls"))`). Strona live = `op.get_absolute_url()`.
- Wzorzec referencyjny (kopiować 1:1 z korektą nazw): `src/import_punktacji_zrodel/`.

---

## File Structure

- `src/import_pracownikow/models.py` — Modify: klasa `ImportPracownikow` na
  `LiveOperation` + pole `stan` + `run`/`on_restart`; `ImportPracownikowRow` — 6 FK
  `null=True` + pola `diff_do_utworzenia`, `pominiety_bo_nieaktualny`. Logika analizy/
  integracji przeniesiona do `pipeline/`.
- `src/import_pracownikow/pipeline/__init__.py` — Create.
- `src/import_pracownikow/pipeline/analyze.py` — Create: `analizuj(parent, p)` —
  dry-run, odroczone create'y.
- `src/import_pracownikow/pipeline/integrate.py` — Create: `integruj(parent, p)` —
  materializacja create'ów + `row.integrate()` + re-check.
- `src/import_pracownikow/views.py` — Modify: widoki na liveops.
- `src/import_pracownikow/urls.py` — Modify: usunąć router/details, restart → POST.
- `src/import_pracownikow/migrations/0010_liveops.py` — Create: migracja bazy operacji.
- `src/import_pracownikow/migrations/0011_row_nullable_diff.py` — Create.
- `src/import_pracownikow/management/commands/usun_stare_pliki_importu_pracownikow.py`
  — Create (DD1).
- `src/import_pracownikow/templates/import_pracownikow/import_pracownikow.html` —
  Create (host-page liveops).
- `src/import_pracownikow/templates/import_pracownikow/import_pracownikow_result.html`
  — Create (fragment wyniku).
- `src/import_pracownikow/tests/` — Modify/Create testy.

---

## Task 1: Migracja modelu operacji na `LiveOperation`

**Files:**
- Modify: `src/import_pracownikow/models.py:2-80` (importy, klasa `ImportPracownikow`
  do metody `perform`)
- Create: `src/import_pracownikow/migrations/0010_liveops.py`
- Test: `src/import_pracownikow/tests/test_models/test_liveops_model.py`

**Interfaces:**
- Produces: `ImportPracownikow(LiveOperation)` z polami `plik_xls` (bez zmian),
  `stan: CharField` (choices `STAN_*`), atrybutem `stages = ["Wczytywanie",
  "Integracja"]`, metodami `run(self, p)`, `on_restart(self)`. Stałe:
  `STAN_UTWORZONY="utworzony"`, `STAN_PRZEANALIZOWANY="przeanalizowany"`,
  `STAN_ZATWIERDZONY="zatwierdzony"`, `STAN_ZINTEGROWANY="zintegrowany"`,
  `STAN_PORZUCONY="porzucony"`.
- Consumes: `pipeline.analyze.analizuj`, `pipeline.integrate.integruj` (Taski 3–4;
  w tym tasku dyspozytor woła je przez lokalny import, funkcje powstają w kolejnych
  taskach — na razie `run` może wołać placeholdery zdefiniowane w Task 3/4; TU testujemy
  tylko istnienie pól i dyspozytor po `stan` z atrapą).

- [ ] **Step 1: Napisz failing test dla dyspozytora `run` i pola `stan`**

```python
# src/import_pracownikow/tests/test_models/test_liveops_model.py
import pytest
from model_bakery import baker
from liveops.models import LiveOperation
from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_jest_liveoperation_z_polem_stan():
    imp = baker.make(ImportPracownikow)
    assert isinstance(imp, LiveOperation)
    assert imp.stan == ImportPracownikow.STAN_UTWORZONY
    # pola po long_running zniknęły:
    assert not hasattr(imp, "performed")
    assert not hasattr(imp, "integrated")


@pytest.mark.django_db
def test_run_dispatch_po_stanie(monkeypatch):
    wywolane = []
    monkeypatch.setattr(
        "import_pracownikow.pipeline.analyze.analizuj",
        lambda parent, p: wywolane.append("analiza"),
    )
    monkeypatch.setattr(
        "import_pracownikow.pipeline.integrate.integruj",
        lambda parent, p: wywolane.append("integracja"),
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.run(p=object())
    imp.stan = ImportPracownikow.STAN_ZATWIERDZONY
    imp.run(p=object())
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY

    class _P:
        def log(self, s):
            wywolane.append(f"log:{s}")

    imp.run(p=_P())
    assert wywolane[0] == "analiza"
    assert wywolane[1] == "integracja"
    assert wywolane[2].startswith("log:")  # no-op z logiem
```

- [ ] **Step 2: Uruchom test — ma FAILOWAĆ**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_liveops_model.py -v`
Expected: FAIL (import `LiveOperation` / brak pola `stan` / `pipeline` nie istnieje).

- [ ] **Step 3: Utwórz `pipeline/` z placeholderami**

```python
# src/import_pracownikow/pipeline/__init__.py
```

```python
# src/import_pracownikow/pipeline/analyze.py
def analizuj(parent, p):
    """Faza analizy (dry-run). Pełna implementacja w Task 3."""
    raise NotImplementedError
```

```python
# src/import_pracownikow/pipeline/integrate.py
def integruj(parent, p):
    """Faza integracji (commit). Pełna implementacja w Task 4."""
    raise NotImplementedError
```

- [ ] **Step 4: Przerób klasę `ImportPracownikow` w `models.py`**

Usuń importy (`models.py:43-44`):
```python
from long_running.models import Operation
from long_running.notification_mixins import ASGINotificationMixin
```
Dodaj na górze (obok innych importów):
```python
from liveops.models import LiveOperation
```
Zamień nagłówek klasy i pola (`models.py:70-80`, blok `class ImportPracownikow(...)`
do końca `on_reset`) na:
```python
class ImportPracownikow(LiveOperation):
    STAN_UTWORZONY = "utworzony"
    STAN_PRZEANALIZOWANY = "przeanalizowany"
    STAN_ZATWIERDZONY = "zatwierdzony"
    STAN_ZINTEGROWANY = "zintegrowany"
    STAN_PORZUCONY = "porzucony"
    STAN_CHOICES = [
        (STAN_UTWORZONY, "utworzony"),
        (STAN_PRZEANALIZOWANY, "przeanalizowany (dry-run gotowy)"),
        (STAN_ZATWIERDZONY, "zatwierdzony do zapisu"),
        (STAN_ZINTEGROWANY, "zintegrowany"),
        (STAN_PORZUCONY, "porzucony"),
    ]

    plik_xls = models.FileField(upload_to="protected/import_pracownikow/")
    stan = models.CharField(
        max_length=20, choices=STAN_CHOICES, default=STAN_UTWORZONY
    )

    stages = ["Wczytywanie", "Integracja"]

    def run(self, p):
        if self.stan == self.STAN_UTWORZONY:
            from import_pracownikow.pipeline.analyze import analizuj

            analizuj(self, p)
        elif self.stan == self.STAN_ZATWIERDZONY:
            from import_pracownikow.pipeline.integrate import integruj

            integruj(self, p)
        else:
            p.log(f"run() w nieoczekiwanym stanie: {self.stan!r} — pomijam")

    def on_restart(self):
        # kasujemy wiersze TYLKO przy ponownej analizie (stan cofnięty do utworzony)
        if self.stan == self.STAN_UTWORZONY:
            self.importpracownikowrow_set.all().delete()
```

Usuń stare metody `perform` (`:237-251`), `on_finished` (`:318-319`) oraz auto-wołanie
`integrate()` — samo `integrate()` jako metoda znika (logika idzie do `pipeline/`).
`get_details_set`, `autorzy_spoza_pliku_set`, `odepnij_autorow_spoza_pliku`,
`zmiany_potrzebne_set` — ZOSTAJĄ bez zmian. `_przetworz_wiersz` i helpery matchujące
— zostają na razie (przeniesione/zmodyfikowane w Task 3).

- [ ] **Step 5: Wygeneruj migrację bazy operacji**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --name liveops`
Expected: utworzony `0010_liveops.py` z: `AlterModelOptions(ordering=('-created_on',))`,
`RemoveField(last_updated_on)`, `RemoveField(performed)`, `RemoveField(integrated)`,
`AddField` dla `cancel_requested, cancelled, current_stage, language, log, log_seq,
percent, result_context, stage_states, status_text, stan`,
`AlterField(owner, related_name='+')`. Zweryfikuj zawartość wg wzorca
`src/import_punktacji_zrodel/migrations/0002_alter_importpunktacjizrodel_options_and_more.py`.

**RĘCZNIE dodaj data-migration (spec §11)** — stare rekordy muszą dostać poprawny
`stan` ZANIM `performed`/`integrated` znikną. W wygenerowanym `0010_liveops.py`
wstaw `RunPython` **po** `AddField(stan)` a **przed** `RemoveField(performed)` /
`RemoveField(integrated)` (kolejność operacji w liście ma znaczenie):
```python
def _ustaw_stan(apps, schema_editor):
    Model = apps.get_model("import_pracownikow", "ImportPracownikow")
    Model.objects.filter(performed=True, integrated=True).update(stan="zintegrowany")
    Model.objects.exclude(performed=True, integrated=True).update(stan="porzucony")


def _wstecz(apps, schema_editor):
    pass  # pola performed/integrated już usunięte — brak sensownego wstecz
```
i w `operations` (po AddField stan, przed RemoveField performed/integrated):
`migrations.RunPython(_ustaw_stan, _wstecz),`

- [ ] **Step 6: Uruchom test — ma PRZEJŚĆ**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_liveops_model.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/pipeline/ \
  src/import_pracownikow/migrations/0010_liveops.py \
  src/import_pracownikow/tests/test_models/test_liveops_model.py
git commit -m "feat(import_pracownikow): model na LiveOperation + pole stan + dyspozytor run (Faza 0 T1)"
```

---

## Task 2: Nullable FK + pola odroczenia na `ImportPracownikowRow`

**Files:**
- Modify: `src/import_pracownikow/models.py:340-352` (pola FK `ImportPracownikowRow`)
- Create: `src/import_pracownikow/migrations/0011_row_nullable_diff.py`
- Test: `src/import_pracownikow/tests/test_models/test_row_nullable.py`

**Interfaces:**
- Produces: `ImportPracownikowRow` z `autor, jednostka, autor_jednostka,
  funkcja_autora, grupa_pracownicza, wymiar_etatu` jako `null=True`; nowe pola
  `diff_do_utworzenia = JSONField(default=dict)`, `pominiety_bo_nieaktualny =
  BooleanField(default=False)`.

- [ ] **Step 1: Napisz failing test**

```python
# src/import_pracownikow/tests/test_models/test_row_nullable.py
import pytest
from model_bakery import baker
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_row_dopuszcza_null_fk_i_ma_pola_odroczenia():
    parent = baker.make(ImportPracownikow)
    row = ImportPracownikowRow.objects.create(
        parent=parent,
        autor=None,
        jednostka=None,
        autor_jednostka=None,
        funkcja_autora=None,
        grupa_pracownicza=None,
        wymiar_etatu=None,
        zmiany_potrzebne=False,
    )
    assert row.pk is not None
    assert row.diff_do_utworzenia == {}
    assert row.pominiety_bo_nieaktualny is False
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_row_nullable.py -v`
Expected: FAIL (IntegrityError / brak pól).

- [ ] **Step 3: Zmień pola FK i dodaj nowe pola**

W `models.py` (`:340-352`) na `ImportPracownikowRow`:
```python
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, null=True, blank=True)
    jednostka = models.ForeignKey(
        Jednostka, on_delete=models.CASCADE, null=True, blank=True
    )
    autor_jednostka = models.ForeignKey(
        Autor_Jednostka, on_delete=models.CASCADE, null=True, blank=True
    )

    podstawowe_miejsce_pracy = models.BooleanField(null=True, blank=True, default=None)
    funkcja_autora = models.ForeignKey(
        Funkcja_Autora, on_delete=models.CASCADE, null=True, blank=True
    )
    grupa_pracownicza = models.ForeignKey(
        Grupa_Pracownicza, on_delete=models.CASCADE, null=True, blank=True
    )
    wymiar_etatu = models.ForeignKey(
        Wymiar_Etatu, on_delete=models.CASCADE, null=True, blank=True
    )
    tytul = models.ForeignKey(Tytul, on_delete=models.SET_NULL, null=True)

    zmiany_potrzebne = models.BooleanField()

    diff_do_utworzenia = models.JSONField(default=dict, blank=True)
    pominiety_bo_nieaktualny = models.BooleanField(default=False)

    log_zmian = JSONField(encoder=DjangoJSONEncoder, null=True, blank=True)
```

- [ ] **Step 4: Migracja**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --name row_nullable_diff`
Expected: `0011_row_nullable_diff.py` z `AlterField` (6 FK → null) + `AddField`
(`diff_do_utworzenia`, `pominiety_bo_nieaktualny`).

- [ ] **Step 5: Uruchom — PASS**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_row_nullable.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/migrations/0011_row_nullable_diff.py \
  src/import_pracownikow/tests/test_models/test_row_nullable.py
git commit -m "feat(import_pracownikow): nullable FK + diff_do_utworzenia na Row (Faza 0 T2)"
```

---

## Task 3: Faza analizy (dry-run, odroczone create'y)

**Files:**
- Create: `src/import_pracownikow/pipeline/analyze.py` (pełna implementacja)
- Modify: `src/import_pracownikow/models.py` — przenieść helpery matchujące
  (`_matchuj_jednostke`, `_waliduj_autora`, `_matchuj_autora_z_walidacja`,
  `_znajdz_autor_jednostka` itd.) lub udostępnić je analizie; wariant „no-create".
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze.py`

**Interfaces:**
- Produces: `analizuj(parent, p) -> None` — iteruje `XLSImportFile(parent.plik_xls.path)`,
  dla każdego wiersza matchuje (jednostka/autor po istniejącym API), a brakujące
  słowniki (Funkcja/Grupa/Wymiar) i `Autor_Jednostka` **NIE tworzy** — zapisuje do
  `row.diff_do_utworzenia`. Na końcu ustawia `parent.stan =
  STAN_PRZEANALIZOWANY`, `parent.save()` i woła `p.result({...})`.
- Consumes: `import_common.core.matchuj_jednostke`, `matchuj_funkcja_autora`,
  `matchuj_grupa_pracownicza`, `matchuj_wymiar_etatu` (czyste `.get()`),
  `matchuj_autora`; `import_common.util.XLSImportFile`; `AutorForm`/`JednostkaForm`.

- [ ] **Step 1: Napisz failing test — dry-run NIC nie pisze do domeny**

```python
# src/import_pracownikow/tests/test_pipeline/test_analyze.py
import pytest
from unittest.mock import patch
from model_bakery import baker
from liveops.testing import MockProgress

from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.analyze import analizuj


def _wiersz(**over):
    base = {
        "nazwisko": "Kowalski",
        "imię": "Jan",
        "nazwa_jednostki": "Katedra Testowa",
        "wydział": "Wydział Testowy",
        "tytuł_stopień": "dr",
        "stanowisko": "Asystent",
        "grupa_pracownicza": "Badawczo-dydaktyczna",
        "data_zatrudnienia": "2016-10-01",
        "wymiar_etatu": "Pełny etat",
        "podstawowe_miejsce_pracy": "TAK",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    base.update(over)
    return base


@pytest.mark.django_db
def test_analiza_nie_tworzy_slownikow_ani_autor_jednostka(dwa_autory_z_jednostka):
    autor, jednostka = dwa_autory_z_jednostka  # fixture zwraca (Autor, Jednostka)
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"

    with patch(
        "import_pracownikow.pipeline.analyze.XLSImportFile"
    ) as MockXIF:
        inst = MockXIF.return_value
        inst.count.return_value = 1
        inst.data.return_value = iter(
            [_wiersz(nazwisko=autor.nazwisko, imię=autor.imiona,
                     nazwa_jednostki=jednostka.nazwa,
                     stanowisko="NIEISTNIEJACE_STANOWISKO_XYZ")]
        )
        przed = Funkcja_Autora.objects.count()
        analizuj(imp, MockProgress(imp))

    # Faza analizy nie utworzyła nowego stanowiska:
    assert Funkcja_Autora.objects.count() == przed
    row = imp.importpracownikowrow_set.get()
    assert row.funkcja_autora is None
    assert "funkcja_autora" in row.diff_do_utworzenia
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
```

Dodaj fixture `dwa_autory_z_jednostka` do `src/import_pracownikow/tests/conftest.py`
(jeśli brak analogicznego) tworzącą `Jednostka` + `Autor` przez `baker.make` z
powiązaniem `Autor_Jednostka`, tak by `matchuj_autora`/`matchuj_jednostke` je znalazły.

- [ ] **Step 2: Uruchom — FAIL**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze.py -v`
Expected: FAIL (`analizuj` to placeholder `NotImplementedError`).

- [ ] **Step 3: Zaimplementuj `analizuj` (wariant no-create)**

```python
# src/import_pracownikow/pipeline/analyze.py
from copy import copy
from datetime import date

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from bpp.models import (
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Tytul,
    Wymiar_Etatu,
)
from import_common.core import (
    matchuj_autora,
    matchuj_funkcja_autora,
    matchuj_grupa_pracownicza,
    matchuj_jednostke,
    matchuj_wymiar_etatu,
)
from import_common.exceptions import XLSMatchError, XLSParseError
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_nullboleanfield,
    normalize_wymiar_etatu,
)
from import_common.util import XLSImportFile
from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowRow,
    JednostkaForm,
)


def _matchuj_slownik_lub_odroc(matcher, wartosc, normalizer, diff, klucz):
    """Zwraca (obiekt|None). Gdy brak w bazie: None + zapis do diff (NIE tworzy)."""
    if not wartosc:
        return None
    try:
        return matcher(wartosc)
    except ObjectDoesNotExist:
        # brak w bazie — odraczamy create do fazy integracji (dry-run nic nie pisze)
        diff[klucz] = normalizer(wartosc)
        return None


def _przetworz_wiersz(parent, elem):
    jednostka_form = JednostkaForm(data=elem)
    jednostka_form.full_clean()
    if not jednostka_form.is_valid():
        raise XLSParseError(elem, jednostka_form, "weryfikacja nazwy jednostki")
    jednostka = matchuj_jednostke(
        jednostka_form.cleaned_data.get("nazwa_jednostki"),
        wydzial=jednostka_form.cleaned_data.get("wydział"),
    )

    autor_form = AutorForm(data=elem)
    autor_form.full_clean()
    if not autor_form.is_valid():
        raise XLSParseError(elem, autor_form, "weryfikacja danych autora")
    data = autor_form.cleaned_data
    tytul_str = data.get("tytuł_stopień")

    diff = {}
    funkcja = _matchuj_slownik_lub_odroc(
        matchuj_funkcja_autora, data.get("stanowisko"),
        normalize_funkcja_autora, diff, "funkcja_autora",
    )
    grupa = _matchuj_slownik_lub_odroc(
        matchuj_grupa_pracownicza, data.get("grupa_pracownicza"),
        normalize_grupa_pracownicza, diff, "grupa_pracownicza",
    )
    wymiar = _matchuj_slownik_lub_odroc(
        matchuj_wymiar_etatu, data.get("wymiar_etatu"),
        normalize_wymiar_etatu, diff, "wymiar_etatu",
    )

    autor = matchuj_autora(
        imiona=data.get("imię"), nazwisko=data.get("nazwisko"),
        jednostka=jednostka, bpp_id=data.get("bpp_id"),
        pbn_uid_id=data.get("pbn_uuid"), system_kadrowy_id=data.get("numer"),
        pbn_id=data.get("pbn_id"), orcid=data.get("orcid"), tytul_str=tytul_str,
    )
    if autor is None:
        raise XLSMatchError(elem, "autor", "brak dopasowania - różne kombinacje")
    if data.get("bpp_id") is not None and data.get("bpp_id") != autor.pk:
        raise XLSMatchError(elem, "autor", "BPP ID nie zgadza się")

    # Autor_Jednostka: match bez tworzenia
    aj = Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).first()
    if aj is None:
        diff["autor_jednostka"] = {"autor": autor.pk, "jednostka": jednostka.pk}

    tytul = None
    if tytul_str:
        try:
            tytul = Tytul.objects.get(Q(nazwa=tytul_str) | Q(skrot=tytul_str))
        except Tytul.DoesNotExist:
            pass

    row = ImportPracownikowRow(
        parent=parent, dane_z_xls=elem,
        dane_znormalizowane=copy(autor_form.cleaned_data),
        autor=autor, jednostka=jednostka, autor_jednostka=aj, tytul=tytul,
        funkcja_autora=funkcja, grupa_pracownicza=grupa, wymiar_etatu=wymiar,
        podstawowe_miejsce_pracy=normalize_nullboleanfield(
            elem.get("podstawowe_miejsce_pracy")
        ),
        diff_do_utworzenia=diff, zmiany_potrzebne=False,
    )
    # zmiany_potrzebne liczymy tylko gdy AJ istnieje (inaczej i tak będzie create):
    if aj is not None:
        row.zmiany_potrzebne = row.check_if_integration_needed()
    else:
        row.zmiany_potrzebne = True
    row.save()


def analizuj(parent, p):
    xif = XLSImportFile(parent.plik_xls.path)
    total = xif.count()
    if total == 0:
        raise ValueError("Plik nie zawiera danych do importu (0 wierszy).")
    for elem in p.track(list(xif.data()), total=total, label="Wczytywanie"):
        _przetworz_wiersz(parent, elem)

    parent.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
    parent.save(update_fields=["stan"])

    wiersze = parent.get_details_set()
    p.result({
        "total": wiersze.count(),
        "zmiany_potrzebne": parent.zmiany_potrzebne_set.count(),
        "byl_dry_run": True,
        "stan": parent.stan,
    })
```

Uwaga: `AutorForm`/`JednostkaForm` są zdefiniowane w `models.py` (`:47-67`) — importuj
je stamtąd. `matchuj_jednostke` może rzucić `Jednostka.DoesNotExist/
MultipleObjectsReturned` — w Fazie 0 zachowujemy zachowanie jak w oryginale (wyjątek
propaguje do runnera → error state); pełna obsługa błędów per-wiersz to późniejsze fazy.

- [ ] **Step 4: Uruchom — PASS**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze.py -v`
Expected: PASS.

- [ ] **Step 5: Uruchom też test brzegowy pustego pliku**

Dodaj do `test_analyze.py`:
```python
@pytest.mark.django_db
def test_pusty_plik_rzuca_jawny_blad():
    imp = baker.make(ImportPracownikow)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"
    with patch("import_pracownikow.pipeline.analyze.XLSImportFile") as MockXIF:
        MockXIF.return_value.count.return_value = 0
        MockXIF.return_value.data.return_value = iter([])
        with pytest.raises(ValueError, match="0 wierszy"):
            analizuj(imp, MockProgress(imp))
```
Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze.py -v`
Expected: PASS (oba testy).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/tests/test_pipeline/ src/import_pracownikow/tests/conftest.py
git commit -m "feat(import_pracownikow): faza analizy dry-run z odroczonymi create (Faza 0 T3)"
```

---

## Task 4: Faza integracji (commit) — materializacja create'ów + re-check

**Files:**
- Create: `src/import_pracownikow/pipeline/integrate.py`
- Test: `src/import_pracownikow/tests/test_pipeline/test_integrate.py`

**Interfaces:**
- Produces: `integruj(parent, p) -> None` — dla każdego wiersza `zmiany_potrzebne=True`:
  materializuje `diff_do_utworzenia` (tworzy Funkcja/Grupa/Wymiar/`Autor_Jednostka`),
  ustawia FK, robi świeży `row.check_if_integration_needed()` (nieaktualne →
  `pominiety_bo_nieaktualny=True`, skip), inaczej `row.integrate()`. Na końcu
  `parent.stan = STAN_ZINTEGROWANY`, `p.result({...})`.
- Consumes: `ImportPracownikowRow.integrate()` (istniejące, `models.py:488`),
  `Funkcja_Autora`/`Grupa_Pracownicza`/`Wymiar_Etatu`/`Autor_Jednostka`.

- [ ] **Step 1: Napisz failing test — commit tworzy i integruje**

```python
# src/import_pracownikow/tests/test_pipeline/test_integrate.py
import pytest
from django.db import transaction
from model_bakery import baker
from liveops.testing import MockProgress

from bpp.models import Autor_Jednostka, Funkcja_Autora
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_commit_materializuje_odroczone_create(autor_jednostka_fixture):
    autor, jednostka = autor_jednostka_fixture
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    row = ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=jednostka,
        autor_jednostka=None, funkcja_autora=None,
        grupa_pracownicza=None, wymiar_etatu=None, tytul=None,
        dane_znormalizowane={"stanowisko": "Asystent"},
        diff_do_utworzenia={
            "funkcja_autora": "asystent",
            "autor_jednostka": {"autor": autor.pk, "jednostka": jednostka.pk},
        },
        zmiany_potrzebne=True,
    )
    integruj(imp, MockProgress(imp))
    row.refresh_from_db()
    assert row.funkcja_autora is not None
    assert Funkcja_Autora.objects.filter(nazwa__iexact="asystent").exists()
    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).exists()
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate.py -v`
Expected: FAIL (placeholder `NotImplementedError`).

- [ ] **Step 3: Zaimplementuj `integruj`**

```python
# src/import_pracownikow/pipeline/integrate.py
from django.db import transaction

from bpp.models import (
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Wymiar_Etatu,
)
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_wymiar_etatu,
)
from import_pracownikow.models import ImportPracownikow


def _materializuj_diff(row):
    diff = row.diff_do_utworzenia or {}
    if "funkcja_autora" in diff:
        nazwa = normalize_funkcja_autora(diff["funkcja_autora"])
        row.funkcja_autora, _ = Funkcja_Autora.objects.get_or_create(
            nazwa=nazwa, defaults={"skrot": nazwa}
        )
    if "grupa_pracownicza" in diff:
        nazwa = normalize_grupa_pracownicza(diff["grupa_pracownicza"])
        row.grupa_pracownicza, _ = Grupa_Pracownicza.objects.get_or_create(nazwa=nazwa)
    if "wymiar_etatu" in diff:
        nazwa = normalize_wymiar_etatu(diff["wymiar_etatu"])
        row.wymiar_etatu, _ = Wymiar_Etatu.objects.get_or_create(nazwa=nazwa)
    if "autor_jednostka" in diff:
        row.autor_jednostka, _ = Autor_Jednostka.objects.get_or_create(
            autor_id=diff["autor_jednostka"]["autor"],
            jednostka_id=diff["autor_jednostka"]["jednostka"],
            defaults={"funkcja": row.funkcja_autora},
        )


def _integruj_wiersz(row):
    with transaction.atomic():
        _materializuj_diff(row)
        row.save(update_fields=[
            "funkcja_autora", "grupa_pracownicza", "wymiar_etatu", "autor_jednostka",
        ])
        # świeży re-check — baza mogła się zmienić od preview:
        if not row.check_if_integration_needed():
            row.pominiety_bo_nieaktualny = True
            row.save(update_fields=["pominiety_bo_nieaktualny"])
            return
        row.integrate()


def integruj(parent, p):
    qs = parent.zmiany_potrzebne_set.all()
    for row in p.track(list(qs), total=qs.count(), label="Integracja"):
        _integruj_wiersz(row)

    parent.stan = ImportPracownikow.STAN_ZINTEGROWANY
    parent.save(update_fields=["stan"])

    p.result({
        "zintegrowano": parent.importpracownikowrow_set.filter(
            log_zmian__isnull=False
        ).count(),
        "pominieto_nieaktualne": parent.importpracownikowrow_set.filter(
            pominiety_bo_nieaktualny=True
        ).count(),
        "stan": parent.stan,
    })
```

Uwaga: `_materializuj_diff` używa `get_or_create` (idempotentne przy duplikatach osoby
w pliku — patrz przypadki brzegowe spec §13). `row.integrate()` (istniejące) asertuje
`zmiany_potrzebne` i loguje do `log_zmian`.

- [ ] **Step 4: Uruchom — PASS**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate.py -v`
Expected: PASS.

- [ ] **Step 5: Test re-check nieaktualnego wiersza**

Dodaj test, w którym `check_if_integration_needed()` zwraca False (np. AJ już ma
docelowe wartości) → `pominiety_bo_nieaktualny=True`, brak `log_zmian`.
Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/pipeline/integrate.py \
  src/import_pracownikow/tests/test_pipeline/test_integrate.py
git commit -m "feat(import_pracownikow): faza integracji + materializacja diff + re-check (Faza 0 T4)"
```

---

## Task 5: Widoki i URL-e na liveops

**Files:**
- Modify: `src/import_pracownikow/views.py` (całość)
- Modify: `src/import_pracownikow/urls.py`
- Modify: `src/import_pracownikow/forms.py` (bez zmian funkcjonalnych — sanity)
- Test: `src/import_pracownikow/tests/test_views_liveops.py`

**Interfaces:**
- Produces: `ListaImportowView`, `NowyImportView`, `ImportPracownikowResultsView`,
  `ImportPracownikowResetujPodstawoweMiejscePracyView`, `ZatwierdzImportView`,
  `RestartAnalizaView`. URL-e: `index`, `new`, `importpracownikow-results`,
  `importpracownikow-resetuj-podstawowe-miejsce-pracy`, `zatwierdz`, `restart-analiza`.
- Consumes: `liveops.views.CreateLiveOperationView`, `RestartView`;
  `braces.views.GroupRequiredMixin`.

- [ ] **Step 1: Napisz failing test — nowy import, zatwierdź, strona live**

```python
# src/import_pracownikow/tests/test_views_liveops.py
import pytest
from unittest.mock import patch
from django.urls import reverse
from model_bakery import baker
from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_strona_live_uzywa_get_absolute_url(admin_client, admin_user):
    imp = baker.make(ImportPracownikow, owner=admin_user)
    url = imp.get_absolute_url()
    assert url == (
        f"/live/import_pracownikow.importpracownikow/{imp.pk}/"
    )
    resp = admin_client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_zatwierdz_ustawia_stan_zatwierdzony_i_reenqueue(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow, owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url)
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZATWIERDZONY
    assert resp.status_code in (204, 302)


@pytest.mark.django_db
def test_restart_analiza_cofa_stan_i_kasuje_wiersze(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow, owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    baker.make("import_pracownikow.ImportPracownikowRow", parent=imp,
               zmiany_potrzebne=False)
    url = reverse("import_pracownikow:restart-analiza", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        admin_client.post(url)
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_UTWORZONY
    assert imp.importpracownikowrow_set.count() == 0  # on_restart skasował
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `uv run pytest src/import_pracownikow/tests/test_views_liveops.py -v`
Expected: FAIL (stare widoki / brak URL `zatwierdz`).

- [ ] **Step 3: Przepisz `views.py`**

```python
# src/import_pracownikow/views.py
from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import ListView
from liveops.views import CreateLiveOperationView, RestartView

from bpp.models import Uczelnia
from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow

GROUP_REQUIRED = "wprowadzanie danych"


class ListaImportowView(GroupRequiredMixin, ListView):
    group_required = GROUP_REQUIRED
    model = ImportPracownikow
    template_name = "import_pracownikow/importpracownikow_list.html"

    def get_queryset(self):
        return ImportPracownikow.objects.filter(
            owner=self.request.user
        ).order_by("-created_on")


class NowyImportView(GroupRequiredMixin, CreateLiveOperationView):
    group_required = GROUP_REQUIRED
    model = ImportPracownikow
    form_class = NowyImportForm


class ImportPracownikowResultsView(GroupRequiredMixin, ListView):
    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/importpracownikowrow_list.html"
    context_object_name = "object_list"

    @property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            from django.http import Http404

            raise Http404
        return obj

    def get_queryset(self):
        return self.parent_object.get_details_set()

    def autorzy_spoza_pliku(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        return self.parent_object.autorzy_spoza_pliku_set(
            uczelnia=uczelnia
        ).select_related("autor", "autor__tytul", "jednostka", "jednostka__wydzial")

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            parent_object=self.parent_object,
            autorzy_spoza_pliku=self.autorzy_spoza_pliku(),
            **kwargs,
        )


class ImportPracownikowResetujPodstawoweMiejscePracyView(
    ImportPracownikowResultsView
):
    def get(self, request, *args, **kwargs):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        self.parent_object.odepnij_autorow_spoza_pliku(uczelnia=uczelnia)
        messages.info(
            request, "Podstawowe miejsca pracy autorów zostały zaktualizowane."
        )
        return HttpResponseRedirect("..")


class _PkOwnerRestartMixin(RestartView):
    model = ImportPracownikow

    def get_object(self, queryset=None):
        return get_object_or_404(
            ImportPracownikow, pk=self.kwargs["pk"], owner=self.request.user
        )


class ZatwierdzImportView(_PkOwnerRestartMixin):
    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.stan = ImportPracownikow.STAN_ZATWIERDZONY
        obj.save(update_fields=["stan"])
        return super().post(request, *args, **kwargs)


class RestartAnalizaView(_PkOwnerRestartMixin):
    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.stan = ImportPracownikow.STAN_UTWORZONY
        obj.save(update_fields=["stan"])
        return super().post(request, *args, **kwargs)
```

- [ ] **Step 4: Przepisz `urls.py`**

```python
# src/import_pracownikow/urls.py
from django.urls import path

from import_pracownikow import views

app_name = "import_pracownikow"

urlpatterns = [
    path("", views.ListaImportowView.as_view(), name="index"),
    path("new/", views.NowyImportView.as_view(), name="new"),
    path(
        "<uuid:pk>/rezultaty/",
        views.ImportPracownikowResultsView.as_view(),
        name="importpracownikow-results",
    ),
    path(
        "<uuid:pk>/resetuj-podstawowe-miejsce-pracy/",
        views.ImportPracownikowResetujPodstawoweMiejscePracyView.as_view(),
        name="importpracownikow-resetuj-podstawowe-miejsce-pracy",
    ),
    path(
        "<uuid:pk>/zatwierdz/",
        views.ZatwierdzImportView.as_view(),
        name="zatwierdz",
    ),
    path(
        "<uuid:pk>/restart-analiza/",
        views.RestartAnalizaView.as_view(),
        name="restart-analiza",
    ),
]
```

- [ ] **Step 5: Uruchom — PASS**

Run: `uv run pytest src/import_pracownikow/tests/test_views_liveops.py -v`
Expected: PASS. (Wymaga host-page template z Task 6 dla `test_strona_live...` —
jeśli test 1 failuje na braku template, przenieś jego uruchomienie za Task 6.)

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/tests/test_views_liveops.py
git commit -m "feat(import_pracownikow): widoki i URL-e na liveops + Zatwierdz/RestartAnaliza (Faza 0 T5)"
```

---

## Task 6: Szablony liveops (host-page + fragment wyniku + listy)

**Files:**
- Create: `src/import_pracownikow/templates/import_pracownikow/import_pracownikow.html`
- Create:
  `src/import_pracownikow/templates/import_pracownikow/import_pracownikow_result.html`
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/importpracownikow_list.html`
  (link `-router` → `get_absolute_url`)
- Modify:
  `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
  (usunąć `{% include "long_running/operation_details.html" %}`)

**Interfaces:**
- Produces: host-page o nazwie `import_pracownikow.html` (= snake_case klasy)
  renderujący `{% live_operation object %}`; fragment `import_pracownikow_result.html`
  renderowany z `result_context` (link do wyników).

- [ ] **Step 1: Utwórz host-page (wzorzec `import_punktacji_zrodel.html`)**

```django
{# src/import_pracownikow/templates/import_pracownikow/import_pracownikow.html #}
{% extends "base.html" %}
{% load static liveops %}
{% block content %}
  <h1>Import pracowników</h1>
  {% live_operation object %}
{% endblock %}
```
(Skrypty htmx/notifications/liveops ładuje tag `{% live_operation %}` /
`liveops/operation.html`; zweryfikuj wobec `import_punktacji_zrodel.html`, skopiuj
ewentualne dodatkowe `{% block %}`/skrypty 1:1.)

- [ ] **Step 2: Utwórz fragment wyniku**

```django
{# src/import_pracownikow/templates/import_pracownikow/import_pracownikow_result.html #}
{% load i18n %}
<div class="callout success">
  <p>Analiza zakończona. Wierszy: {{ result_context.total }},
     do zmiany: {{ result_context.zmiany_potrzebne }}.</p>
  {% if result_context.byl_dry_run %}
    <p>To był podgląd (dry-run) — nic nie zapisano do bazy.</p>
    <form method="post"
          action="{% url 'import_pracownikow:zatwierdz' object.pk %}">
      {% csrf_token %}
      <button class="button" type="submit">Zapisz zmiany do bazy</button>
    </form>
  {% endif %}
  <a class="button secondary"
     href="{% url 'import_pracownikow:importpracownikow-results' object.pk %}">
    Zobacz szczegóły wierszy
  </a>
</div>
```

- [ ] **Step 3: Popraw link w `importpracownikow_list.html`**

Zamień `{% url 'import_pracownikow:importpracownikow-router' ... %}` (linia ~24) na
`{{ obiekt.get_absolute_url }}` (użyj właściwej nazwy zmiennej pętli z tego szablonu).

- [ ] **Step 4: Usuń long_running include z `importpracownikowrow_list.html`**

Usuń `{% include "long_running/operation_details.html" %}` (linia ~17); zostaw tabelę
wyników renderowaną z `object_list` + sekcję `autorzy_spoza_pliku`.

- [ ] **Step 5: Uruchom testy widoków (w tym host-page)**

Run: `uv run pytest src/import_pracownikow/tests/test_views_liveops.py -v`
Expected: PASS (wszystkie 3 testy, w tym `test_strona_live_uzywa_get_absolute_url`).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/templates/import_pracownikow/
git commit -m "feat(import_pracownikow): szablony liveops host-page + fragment wyniku (Faza 0 T6)"
```

---

## Task 7: Aktualizacja istniejących testów i fixture

**Files:**
- Modify: `src/import_pracownikow/tests/conftest.py:75-77` (fixture
  `import_pracownikow_performed`)
- Modify: `src/import_pracownikow/tests/test_models/test_models.py` (`.perform()`,
  `.mark_reset()`)
- Modify: ewentualne pozostałe testy używające `perform`/`integrated`/`performed`.

**Interfaces:**
- Consumes: `analizuj`/`integruj`, `MockProgress`, `ImportPracownikow.run`.

- [ ] **Step 1: Zmapuj miejsca do zmiany**

Run: `grep -rn "\.perform()\|\.mark_reset()\|performed\|integrated\|send_progress" src/import_pracownikow/tests/`
Expected: lista wystąpień.

- [ ] **Step 2: Zaktualizuj fixture `import_pracownikow_performed`**

W `conftest.py` zamień `import_pracownikow.perform()` na pełny przebieg dry-run+commit:
```python
from liveops.testing import MockProgress

@pytest.fixture
def import_pracownikow_performed(import_pracownikow):
    import_pracownikow.stan = import_pracownikow.STAN_UTWORZONY
    import_pracownikow.run(MockProgress(import_pracownikow))   # analiza
    import_pracownikow.stan = import_pracownikow.STAN_ZATWIERDZONY
    import_pracownikow.run(MockProgress(import_pracownikow))   # integracja
    import_pracownikow.refresh_from_db()
    return import_pracownikow
```

- [ ] **Step 3: Zaktualizuj `test_models.py`**

Zamień każde `import_pracownikow.perform()` →
`import_pracownikow.run(MockProgress(import_pracownikow))` (z ustawieniem `stan`
zależnie od intencji testu), a `mark_reset()` → ustaw `stan=STAN_UTWORZONY` +
`on_restart()`. Zamień asercje na `performed`/`integrated` na asercje po `stan`.

- [ ] **Step 4: Uruchom testy całej aplikacji**

Run: `uv run pytest src/import_pracownikow/ -v`
Expected: PASS (wszystkie). Napraw ewentualne pozostałe odwołania do starego API.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/tests/
git commit -m "test(import_pracownikow): fixtures i testy na run()+MockProgress (Faza 0 T7)"
```

---

## Task 8: Housekeeping (DD1), ostrzeżenie współbieżności (DD2), baseline, pełne testy

**Files:**
- Create:
  `src/import_pracownikow/management/__init__.py`,
  `src/import_pracownikow/management/commands/__init__.py`,
  `src/import_pracownikow/management/commands/usun_stare_pliki_importu_pracownikow.py`
- Modify: `src/django_bpp/settings/base.py` (dodać `IMPORT_PRACOWNIKOW_RETENCJA_DNI`)
- Modify: `src/import_pracownikow/views.py` (`NowyImportView` — ostrzeżenie DD2)
- Test: `src/import_pracownikow/tests/test_housekeeping.py`

**Interfaces:**
- Produces: management command kasujący blob `plik_xls` starszy niż
  `IMPORT_PRACOWNIKOW_RETENCJA_DNI` (default 90), zostawiający rekord + wiersze.

- [ ] **Step 1: Failing test housekeepingu**

```python
# src/import_pracownikow/tests/test_housekeeping.py
import pytest
from datetime import timedelta
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker
from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_kasuje_stary_blob_zostawia_rekord(settings):
    settings.IMPORT_PRACOWNIKOW_RETENCJA_DNI = 90
    imp = baker.make(ImportPracownikow)
    imp.plik_xls.save("x.xlsx", ContentFile(b"dane"))
    ImportPracownikow.objects.filter(pk=imp.pk).update(
        created_on=timezone.now() - timedelta(days=100)
    )
    call_command("usun_stare_pliki_importu_pracownikow")
    imp.refresh_from_db()
    assert not imp.plik_xls          # blob skasowany
    assert ImportPracownikow.objects.filter(pk=imp.pk).exists()  # rekord został
```

- [ ] **Step 2: Uruchom — FAIL**

Run: `uv run pytest src/import_pracownikow/tests/test_housekeeping.py -v`
Expected: FAIL (brak komendy).

- [ ] **Step 3: Zaimplementuj komendę + setting**

`base.py` (obok innych ustawień aplikacyjnych):
```python
IMPORT_PRACOWNIKOW_RETENCJA_DNI = env.int(
    "IMPORT_PRACOWNIKOW_RETENCJA_DNI", default=90
)
```
```python
# src/import_pracownikow/management/commands/usun_stare_pliki_importu_pracownikow.py
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from import_pracownikow.models import ImportPracownikow


class Command(BaseCommand):
    help = "Kasuje blob plik_xls importów starszych niż retencja (zostawia rekord)."

    def handle(self, *args, **options):
        dni = getattr(settings, "IMPORT_PRACOWNIKOW_RETENCJA_DNI", 90)
        prog = timezone.now() - timedelta(days=dni)
        qs = ImportPracownikow.objects.filter(
            created_on__lt=prog
        ).exclude(plik_xls="")
        n = 0
        for imp in qs:
            imp.plik_xls.delete(save=False)
            imp.plik_xls = ""
            imp.save(update_fields=["plik_xls"])
            n += 1
        self.stdout.write(f"Skasowano blobów: {n}")
```
Utwórz `management/__init__.py` i `management/commands/__init__.py` (puste).

- [ ] **Step 4: Uruchom — PASS**

Run: `uv run pytest src/import_pracownikow/tests/test_housekeeping.py -v`
Expected: PASS.

- [ ] **Step 5: Ostrzeżenie DD2 w `NowyImportView`**

W `NowyImportView` dodaj `get` sprawdzający czy user ma niezatwierdzony import w
`STAN_PRZEANALIZOWANY` i wtedy `messages.warning(...)` (nie blokuje):
```python
    def get(self, request, *args, **kwargs):
        if ImportPracownikow.objects.filter(
            owner=request.user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
        ).exists():
            messages.warning(
                request,
                "Masz niezatwierdzony import w podglądzie — nowa analiza może "
                "unieważnić jego wynik.",
            )
        return super().get(request, *args, **kwargs)
```
(dodaj `from django.contrib import messages` jeśli brak).

- [ ] **Step 6: Odśwież baseline i uruchom pełne testy aplikacji + smoke reszty**

Run: `make baseline-update`
Expected: delta migracji `0010`/`0011` w `baseline-sql/baseline.sql`, bez błędów.

Run: `uv run pytest src/import_pracownikow/ -v`
Expected: PASS (wszystko).

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: „No changes detected" (brak migration drift).

Run: `ruff check src/import_pracownikow/ && ruff format --check src/import_pracownikow/`
Expected: czysto.

- [ ] **Step 7: Commit + baseline**

```bash
git add src/import_pracownikow/management/ src/import_pracownikow/views.py \
  src/import_pracownikow/tests/test_housekeeping.py \
  src/django_bpp/settings/base.py baseline-sql/
git commit -m "feat(import_pracownikow): housekeeping DD1 + ostrzeżenie DD2 + baseline (Faza 0 T8)"
```

---

## Weryfikacja końcowa Fazy 0

- [ ] `uv run pytest src/import_pracownikow/` — zielone.
- [ ] `grep -rn "long_running" src/import_pracownikow/` — brak wyników (poza ewentualnie
  komentarzami historycznymi).
- [ ] Dry-run: nowy import → analiza NIE zapisuje do `Autor`/`Autor_Jednostka`; wyniki
  widoczne w preview; „Zapisz zmiany do bazy" → integracja zapisuje.
- [ ] `makemigrations --check --dry-run` — brak drift.
- [ ] `make baseline-update` scommitowany.

## Uwaga o kolejnych fazach

Fazy 1–5 (CSV+XLSX `TabularSource`, hybrydowe mapowanie kolumn + profile, parser
sklejonej osoby + wskaźnik pewności, „utwórz nowego autora" + odpięcia per-autor,
przepięcie prac + cofanie) dostaną własne plany — każda buduje na Fazie 0. W Fazie 2
dyspozytor `run()` przełącza się z `utworzony→analiza` na `zmapowany→analiza` +
custom `form_valid` bez enqueue + ekran mapowania (patrz spec §14).
