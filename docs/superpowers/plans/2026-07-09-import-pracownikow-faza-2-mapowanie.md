# Import pracowników — Faza 2: hybrydowe mapowanie kolumn + profile

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pozwolić importować pliki z **inaczej nazwanymi / brakującymi
kolumnami** przez ekran mapowania (auto-propozycja + korekta) z zapisywalnymi
profilami, przełączając maszynę stanów tak, że analiza rusza dopiero po
zatwierdzeniu mapowania.

**Architecture:** Po uploadzie widok **synchronicznie** czyta nagłówki + próbkę
(bez liveops) i pokazuje ekran mapowania: każda kolumna pliku → pole systemowe
(dropdown) albo „pomiń". Auto-propozycja przez słownik synonimów (wzorzec
`import_dyscyplin.guess_rodzaj`). Zatwierdzenie zapisuje `mapowanie_kolumn`
(JSON snapshot na imporcie), przechodzi w stan `zmapowany` i **dopiero teraz**
kolejkuje analizę. Analiza (`analizuj`, Faza 0/1) remapuje klucze wiersza wg
mapowania przed walidacją formularzem. Profile (`ProfilMapowania`) pozwalają
zapisać i reużyć mapowanie dla powtarzalnych plików tej samej uczelni.

**Tech Stack:** Django, liveops, crispy-forms (jak `import_dyscyplin`), pytest.

## Global Constraints

- **Max 88 znaków/linia** (ruff); **zawsze `uv run`** dla Pythona.
- **NIE modyfikować istniejących migracji.** Faza 2 dodaje JEDNĄ nową migrację
  (`0012_mapowanie_profile`). **Baseline (`make baseline-update`) NIE na tym
  feature-branchu** — dopiero przy merge (reguła CLAUDE.md).
- **Bez `except: pass`** (wąski typ + komentarz OK).
- **Komentarze szablonów Django `{# #}` jedno-liniowe** — KAŻDA linia własne
  `{# ... #}`. Ikony we froncie publicznym: Foundation-Icons (nie emoji).
- **pytest, nie unittest**; funkcje bez klas; `@pytest.mark.django_db` gdy DB;
  `model_bakery.baker.make`.
- **Backward compat maszyny stanów:** stany Fazy 0 (`utworzony`,
  `przeanalizowany`, `zatwierdzony`, `zintegrowany`, `porzucony`) i przejścia
  commitu (`ZatwierdzImportView`, `RestartAnalizaView`) MUSZĄ dalej działać.
  Stare rekordy (bez `mapowanie_kolumn`) nie mogą się wywalić.
- **Pipeline Fazy 0/1 (analyze/integrate) niezmieniony poza remapowaniem
  kluczy** — dry-run, `dane_z_xls` surowe, deferred creates, re-check integracji.
- **PESEL** (`DEFAULT_BANNED_NAMES`) nigdy nie oferowany jako kolumna do mapowania.

---

## Kontekst i wzorce (przeczytaj przed implementacją)

- **Wzorzec ekranu mapowania:** `src/import_dyscyplin/` — `Kolumna` model,
  `guess_rodzaj(s)` + `_zbuduj_mapowanie_nazw()` (słownik synonimów, `models.py`),
  `KolumnaImport_Dyscyplin` view + `KolumnaFormSet` + template
  `templates/import_dyscyplin/import_dyscyplin_kolumny.html`. Faza 2 naśladuje
  ideę (auto-guess + ekran korekty), ale zapisuje **JSON snapshot**
  (`mapowanie_kolumn`) zamiast sub-modelu `Kolumna`, bo profile i tak są JSON-em.
- **liveops:** `CreateLiveOperationView.form_valid` (`liveops/views.py:101-105`)
  robi `save(); enqueue(); redirect(get_absolute_url())`. Faza 2 nadpisuje:
  `save()` (stan `utworzony`) **bez `enqueue`**, redirect na ekran mapowania.
  `RestartView.post` woła `on_restart()` → reset → `enqueue()`.
- **Stan po Fazie 0/1:** `ImportPracownikow(LiveOperation)` z polem `stan`
  (STAN_UTWORZONY/…); `run(self, p)` dyspozytor; `on_restart()` kasuje wiersze
  gdy `stan==utworzony`. `analizuj()` (Faza 1) czyta przez `otworz_zrodlo` i
  woła `_przetworz_wiersz(parent, elem)` (elem = dict znormalizowanych nagłówek→
  wartość); formularze `JednostkaForm`/`AutorForm` oczekują kluczy
  kanonicznych (`nazwa_jednostki`, `wydział`, `nazwisko`, `imię`,
  `tytuł_stopień`, `stanowisko`, `grupa_pracownicza`, `data_zatrudnienia`,
  `data_końca_zatrudnienia`, `podstawowe_miejsce_pracy`, `wymiar_etatu`, `numer`,
  `orcid`, `pbn_uuid`, `bpp_id`).
- **`otworz_zrodlo(path)` (Faza 1)** zwraca źródło z `count()`/`data()`; klucze
  wiersza to znormalizowane nagłówki pliku + `__xls_loc_sheet__`/`__xls_loc_row__`.

---

## File Structure

**Tworzone:**
- `src/import_pracownikow/mapping.py` — `POLA_DOCELOWE`, `POLE_POMIN`,
  `_SYNONIMY` (wewn.), `TRY_NAMES`/`MIN_POINTS` (dla detekcji nagłówka),
  `zaproponuj_mapowanie`, `waliduj_mapowanie`, `dopasuj_profil`,
  `remapuj_wiersz`.
- `src/import_pracownikow/migrations/0012_mapowanie_profile.py` — pole
  `mapowanie_kolumn`, model `ProfilMapowania`, nowy choice `zmapowany`.
- `src/import_pracownikow/templates/import_pracownikow/mapowanie.html` — ekran.
- `src/import_pracownikow/tests/test_mapping.py`
- `src/import_pracownikow/tests/test_views_mapowanie.py`
- `src/import_pracownikow/tests/test_pipeline/test_analyze_mapowanie.py`
- `src/bpp/newsfragments/import-pracownikow-mapowanie-kolumn.feature.rst`

**Modyfikowane:**
- `src/import_pracownikow/models.py` — `STAN_ZMAPOWANY`, `mapowanie_kolumn`,
  `ProfilMapowania`, `run()` dyspozytor (utworzony→noop, zmapowany→analiza),
  `on_restart()` (kasuje przy `zmapowany`), helper `naglowki_i_probka`.
- `src/import_pracownikow/forms.py` — `MapowanieForm` (dynamiczny),
  `AutorForm`/`JednostkaForm` (pola nie-identyfikacyjne opcjonalne).
- `src/import_pracownikow/views.py` — `NowyImportView.form_valid` (bez enqueue),
  `MapowanieView`, `RestartAnalizaView` (cofa do `zmapowany`, nie `utworzony`).
- `src/import_pracownikow/urls.py` — trasa `mapowanie`.
- `src/import_pracownikow/pipeline/analyze.py` — remap kluczy przez
  `mapowanie_kolumn` przed formularzami.

**Poza zakresem (kolejne fazy — nie flagować jako braki):**
- Parser sklejonej komórki `osoba_sklejona` + wskaźnik pewności + edycja inline
  → **Faza 3** (dlatego `POLA_DOCELOWE` w Fazie 2 NIE zawiera `osoba_sklejona`).
- „Utwórz nowego autora", odpięcia per-autor → **Faza 4**.
- Przepięcie prac → **Faza 5**.
- Walidacja spójności nagłówków między arkuszami XLSX — v1 zakłada spójne
  arkusze (mapowanie jedno na cały import). Świadome ograniczenie: jeśli arkusz
  2 ma inne nagłówki, `remapuj_wiersz` po cichu wytnie jego niepasujące kolumny
  (brak wpisu → `POLE_POMIN`), a wiersz padnie na „brak nazwiska/jednostki".
  Jawna walidacja rozbieżności między arkuszami (spec §5) — **odłożona**; realne
  pliki kadrowe to zwykle jeden arkusz. Jeśli okaże się potrzebna wcześniej —
  dodać porównanie zbiorów nagłówków arkuszy w `naglowki_i_probka`.

---

### Task 1: Model — stan `zmapowany`, `mapowanie_kolumn`, `ProfilMapowania`

**Files:**
- Modify: `src/import_pracownikow/models.py` (STAN_*, pole, model)
- Create: `src/import_pracownikow/migrations/0012_mapowanie_profile.py`
- Test: `src/import_pracownikow/tests/test_models/test_mapowanie_model.py`

**Interfaces:**
- Produces: `ImportPracownikow.STAN_ZMAPOWANY = "zmapowany"`;
  `ImportPracownikow.mapowanie_kolumn` (JSONField, default=dict);
  `ProfilMapowania(nazwa, mapowanie, ostatnio_uzyty, utworzony_przez)`.

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_models/test_mapowanie_model.py`:

```python
import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ProfilMapowania


@pytest.mark.django_db
def test_import_ma_pole_mapowanie_kolumn_domyslnie_puste():
    imp = baker.make(ImportPracownikow)
    assert imp.mapowanie_kolumn == {}


@pytest.mark.django_db
def test_stan_zmapowany_istnieje():
    assert ImportPracownikow.STAN_ZMAPOWANY == "zmapowany"
    kody = [k for k, _ in ImportPracownikow.STAN_CHOICES]
    assert "zmapowany" in kody


@pytest.mark.django_db
def test_profil_mapowania_zapis_i_odczyt(admin_user):
    p = ProfilMapowania.objects.create(
        nazwa="Uczelnia Vizja Q3",
        mapowanie={"jedn_org": "nazwa_jednostki", "nazwisko": "nazwisko"},
        utworzony_przez=admin_user,
    )
    p.refresh_from_db()
    assert p.mapowanie["jedn_org"] == "nazwa_jednostki"
    assert str(p) == "Uczelnia Vizja Q3"
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_mapowanie_model.py -v`
Expected: FAIL (`ImportError: cannot import name 'ProfilMapowania'`).

- [ ] **Step 3: Model — dodaj stan, pole, ProfilMapowania**

W `src/import_pracownikow/models.py`, w klasie `ImportPracownikow`, dodaj stałą
stanu (po `STAN_UTWORZONY`) i choice:

```python
    STAN_UTWORZONY = "utworzony"
    STAN_ZMAPOWANY = "zmapowany"
    STAN_PRZEANALIZOWANY = "przeanalizowany"
```

W `STAN_CHOICES` dodaj (po `utworzony`):

```python
        (STAN_UTWORZONY, "utworzony"),
        (STAN_ZMAPOWANY, "zmapowany (kolumny określone)"),
        (STAN_PRZEANALIZOWANY, "przeanalizowany (dry-run gotowy)"),
```

Po polu `stan` dodaj pole mapowania:

```python
    mapowanie_kolumn = models.JSONField(default=dict, blank=True)
```

Na końcu pliku (po ostatnim modelu) dodaj model profilu:

```python
class ProfilMapowania(models.Model):
    """Zapisywalne mapowanie nagłówków pliku → pola systemowe, do reużycia
    przy powtarzalnych plikach (ta sama uczelnia co kwartał). BPP jest
    single-tenant per instalacja, więc profile są globalne dla instancji."""

    nazwa = models.CharField(max_length=200, unique=True)
    mapowanie = models.JSONField(default=dict)
    ostatnio_uzyty = models.DateTimeField(null=True, blank=True)
    utworzony_przez = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "profil mapowania importu pracowników"
        verbose_name_plural = "profile mapowania importu pracowników"
        ordering = ["nazwa"]

    def __str__(self):
        return self.nazwa
```

Upewnij się, że u góry pliku jest `from django.conf import settings` (dodaj jeśli
brak).

- [ ] **Step 4: Wygeneruj migrację**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --name mapowanie_profile`
Expected: utworzony `0012_mapowanie_profile.py` (AddField mapowanie_kolumn +
CreateModel ProfilMapowania + AlterField stan choices). **NIE** edytuj ręcznie
istniejących migracji.

- [ ] **Step 5: Sprawdź brak driftu**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: „No changes detected".

- [ ] **Step 6: Uruchom testy — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_mapowanie_model.py -v`
Expected: PASS (3).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/migrations/0012_mapowanie_profile.py \
  src/import_pracownikow/tests/test_models/test_mapowanie_model.py
git commit -m "feat(import_pracownikow): stan zmapowany + mapowanie_kolumn + ProfilMapowania (Faza 2 T1)"
```

---

### Task 2: Silnik mapowania — pola docelowe, synonimy, propozycja, walidacja

**Files:**
- Create: `src/import_pracownikow/mapping.py`
- Test: `src/import_pracownikow/tests/test_mapping.py`

**Interfaces:**
- Produces:
  - `POLE_POMIN = "__pomin__"`.
  - `POLA_DOCELOWE: list[tuple[str, str]]` — `(klucz_kanoniczny, etykieta)`;
    klucze = pola formularzy (`nazwa_jednostki`, `wydział`, `nazwisko`, `imię`,
    `numer`, `orcid`, `tytuł_stopień`, `pbn_uuid`, `bpp_id`, `stanowisko`,
    `grupa_pracownicza`, `data_zatrudnienia`, `data_końca_zatrudnienia`,
    `podstawowe_miejsce_pracy`, `wymiar_etatu`).
  - `zaproponuj_mapowanie(naglowki: list[str]) -> dict[str, str]` —
    `{naglowek: pole_docelowe_lub_POLE_POMIN}`.
  - `waliduj_mapowanie(mapowanie: dict) -> list[str]` — lista błędów (pusta = OK).

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_mapping.py`:

```python
from import_pracownikow.mapping import (
    POLA_DOCELOWE,
    POLE_POMIN,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)


def test_pola_docelowe_zawieraja_kluczowe_pola():
    klucze = {k for k, _ in POLA_DOCELOWE}
    assert {"nazwa_jednostki", "wydział", "nazwisko", "imię"} <= klucze
    # osoba_sklejona to Faza 3 — NIE ma jej tu:
    assert "osoba_sklejona" not in klucze


def test_zaproponuj_mapowanie_synonimy():
    naglowki = ["nazwisko", "imię", "jedn_org", "stanowisko", "kolumna_smieciowa"]
    prop = zaproponuj_mapowanie(naglowki)
    assert prop["nazwisko"] == "nazwisko"
    assert prop["imię"] == "imię"
    assert prop["jedn_org"] == "nazwa_jednostki"  # synonim
    assert prop["stanowisko"] == "stanowisko"
    # nieznana kolumna → pomiń
    assert prop["kolumna_smieciowa"] == POLE_POMIN


def test_zaproponuj_mapowanie_bpp_wzorzec():
    # znormalizowane nagłówki wzorca BPP
    naglowki = ["nazwa_jednostki", "wydział", "tytuł_stopień", "bpp_id"]
    prop = zaproponuj_mapowanie(naglowki)
    assert prop["nazwa_jednostki"] == "nazwa_jednostki"
    assert prop["tytuł_stopień"] == "tytuł_stopień"
    assert prop["bpp_id"] == "bpp_id"


def test_waliduj_mapowanie_wymaga_nazwisko_imie_jednostka():
    # brak jednostki → błąd
    bledy = waliduj_mapowanie({"a": "nazwisko", "b": "imię"})
    assert any("jednostk" in e.lower() for e in bledy)
    # komplet identyfikacji → OK
    assert waliduj_mapowanie(
        {"a": "nazwisko", "b": "imię", "c": "nazwa_jednostki"}
    ) == []


def test_waliduj_mapowanie_odrzuca_duplikat_pola():
    # to samo pole docelowe przypisane dwóm kolumnom → błąd
    bledy = waliduj_mapowanie(
        {"a": "nazwisko", "b": "nazwisko", "c": "imię", "d": "nazwa_jednostki"}
    )
    assert any("dwukrotnie" in e.lower() or "duplikat" in e.lower() for e in bledy)
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -v`
Expected: FAIL (`ModuleNotFoundError: ...mapping`).

- [ ] **Step 3: Implementuj `mapping.py` (część 1 — pola/synonimy/propozycja/walidacja)**

Utwórz `src/import_pracownikow/mapping.py`:

```python
"""Silnik mapowania kolumn importu pracowników.

Auto-propozycja mapowania nagłówek pliku → pole systemowe (przez słownik
synonimów, wzorzec ``import_dyscyplin.guess_rodzaj``), walidacja oraz
remapowanie wiersza. Profile (``dopasuj_profil``) w części 2 (Task 3).
"""

POLE_POMIN = "__pomin__"

# Pola docelowe = klucze oczekiwane przez JednostkaForm/AutorForm. Kompozyty
# (osoba_sklejona) NALEŻĄ do Fazy 3 — tu ich nie ma.
POLA_DOCELOWE = [
    ("nazwisko", "Nazwisko"),
    ("imię", "Imię"),
    ("nazwa_jednostki", "Nazwa jednostki"),
    ("wydział", "Wydział"),
    ("tytuł_stopień", "Tytuł / stopień"),
    ("stanowisko", "Stanowisko"),
    ("grupa_pracownicza", "Grupa pracownicza"),
    ("wymiar_etatu", "Wymiar etatu"),
    ("data_zatrudnienia", "Data zatrudnienia"),
    ("data_końca_zatrudnienia", "Data końca zatrudnienia"),
    ("podstawowe_miejsce_pracy", "Podstawowe miejsce pracy"),
    ("numer", "Numer (system kadrowy)"),
    ("orcid", "ORCID"),
    ("pbn_uuid", "PBN UUID"),
    ("bpp_id", "BPP ID"),
]

# Pola identyfikacyjne — mapowanie MUSI zawierać nazwisko+imię ORAZ jednostkę.
_POLA_IDENTYFIKACJI = {"nazwisko", "imię"}
_POLE_JEDNOSTKA = "nazwa_jednostki"

# Synonimy: znormalizowany nagłówek pliku → pole docelowe. Znormalizowany tak
# jak robi to normalize_cell_header (lower, spacje/kropki/myślniki → "_").
_SYNONIMY = {
    "nazwisko": "nazwisko",
    "nazwiska": "nazwisko",
    "imię": "imię",
    "imie": "imię",
    "imiona": "imię",
    "nazwa_jednostki": "nazwa_jednostki",
    "jednostka": "nazwa_jednostki",
    "jedn_org": "nazwa_jednostki",
    "jednostka_organizacyjna": "nazwa_jednostki",
    "komorka_organizacyjna": "nazwa_jednostki",
    "komórka_organizacyjna": "nazwa_jednostki",
    "zaklad": "nazwa_jednostki",
    "zakład": "nazwa_jednostki",
    "klinika": "nazwa_jednostki",
    "katedra": "nazwa_jednostki",
    "wydzial": "wydział",
    "wydział": "wydział",
    "tytuł_stopień": "tytuł_stopień",
    "tytul_stopien": "tytuł_stopień",
    "tytuł___stopień": "tytuł_stopień",  # „Tytuł / Stopień" (spacje wokół /)
    "tytul___stopien": "tytuł_stopień",
    "tytuł": "tytuł_stopień",
    "tytul": "tytuł_stopień",
    "stopień": "tytuł_stopień",
    "stopien": "tytuł_stopień",
    "stanowisko": "stanowisko",
    "grupa_pracownicza": "grupa_pracownicza",
    "grupa": "grupa_pracownicza",
    "wymiar_etatu": "wymiar_etatu",
    "etat": "wymiar_etatu",
    "wymiar": "wymiar_etatu",
    "data_zatrudnienia": "data_zatrudnienia",
    "data_końca_zatrudnienia": "data_końca_zatrudnienia",
    "data_konca_zatrudnienia": "data_końca_zatrudnienia",
    "podstawowe_miejsce_pracy": "podstawowe_miejsce_pracy",
    "numer": "numer",
    "orcid": "orcid",
    "pbn_uuid": "pbn_uuid",
    "pbn_uid": "pbn_uuid",
    "bpp_id": "bpp_id",
}

# Nazwy-kandydaci nagłówka dla ``otworz_zrodlo``. KLUCZOWE dla Fazy 2: fuzzy-
# detekcja nagłówka (``find_similar_row_in_rows``) domyślnie szuka ≥3 nazw z
# ``DEFAULT_COL_NAMES`` (kanonicznych). Plik z przemianowanymi kolumnami (np.
# „Jedn org") nigdy by nie trafił w te 3 → ``HeaderNotFoundException`` PRZED
# ekranem mapowania. Dając wszystkie warianty synonimów jako ``try_names`` +
# ``MIN_POINTS=2`` sprawiamy, że nagłówek z ≥2 rozpoznawalnymi kolumnami (a
# nazwisko+imię są niemal zawsze) jest znajdowany, a dopiero ekran mapowania
# rozstrzyga resztę. **Te same** ``try_names``/``min_points`` MUSZĄ iść do
# ``naglowki_i_probka`` (ekran) I do ``analizuj`` (analiza) — inaczej ekran
# przyjmie plik, którego analiza potem nie otworzy.
TRY_NAMES = sorted(set(_SYNONIMY.keys()))
MIN_POINTS = 2


def zaproponuj_mapowanie(naglowki):
    """Dla listy znormalizowanych nagłówków pliku zwraca słownik
    ``{naglowek: pole_docelowe_lub_POLE_POMIN}`` na podstawie synonimów."""
    return {h: _SYNONIMY.get(h, POLE_POMIN) for h in naglowki}


def waliduj_mapowanie(mapowanie):
    """Zwraca listę błędów (pusta = OK). Reguły:
    - musi być zmapowane ``nazwisko``, ``imię`` oraz ``nazwa_jednostki``;
    - żadne pole docelowe (poza ``POLE_POMIN``) nie może być użyte dwukrotnie."""
    bledy = []
    uzyte = [v for v in mapowanie.values() if v != POLE_POMIN]

    brakujace = _POLA_IDENTYFIKACJI - set(uzyte)
    if brakujace:
        bledy.append(
            "Brak wymaganych pól identyfikacji: "
            + ", ".join(sorted(brakujace))
        )
    if _POLE_JEDNOSTKA not in uzyte:
        bledy.append("Brak wymaganego pola: nazwa jednostki")

    for pole in set(uzyte):
        if uzyte.count(pole) > 1:
            bledy.append(f"Pole '{pole}' przypisane dwukrotnie (duplikat)")

    return bledy
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -v`
Expected: PASS (5).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/mapping.py src/import_pracownikow/tests/test_mapping.py
git commit -m "feat(import_pracownikow): silnik mapowania — synonimy, propozycja, walidacja (Faza 2 T2)"
```

---

### Task 3: Remapowanie wiersza + dopasowanie profilu

**Files:**
- Modify: `src/import_pracownikow/mapping.py`
- Test: `src/import_pracownikow/tests/test_mapping.py`

**Interfaces:**
- Consumes: `POLE_POMIN`, `ProfilMapowania` (Task 1).
- Produces:
  - `remapuj_wiersz(elem: dict, mapowanie: dict) -> dict` — przepisuje klucze
    pliku na kanoniczne wg mapowania; zachowuje `__xls_loc_sheet__`/
    `__xls_loc_row__`; pomija kolumny zmapowane na `POLE_POMIN`.
  - `dopasuj_profil(naglowki: list[str]) -> ProfilMapowania | None` — profil,
    którego zbiór kluczy pokrywa ≥90% znormalizowanych nagłówków pliku.

- [ ] **Step 1: Napisz failing testy**

Importy (`import pytest`, `baker`, `dopasuj_profil`/`remapuj_wiersz`,
`ProfilMapowania`) dodaj do bloku importów NA GÓRZE `test_mapping.py` (nie w
środku — plik `import_pracownikow/tests` JEST lintowany, E402). Testy na końcu:

```python
import pytest
from model_bakery import baker

from import_pracownikow.mapping import dopasuj_profil, remapuj_wiersz
from import_pracownikow.models import ProfilMapowania


def test_remapuj_wiersz_przepisuje_klucze_i_pomija():
    elem = {
        "jedn_org": "Katedra X",
        "nazwisko": "Kowalski",
        "kolumna_smieciowa": "xxx",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    mapowanie = {
        "jedn_org": "nazwa_jednostki",
        "nazwisko": "nazwisko",
        "kolumna_smieciowa": "__pomin__",
    }
    out = remapuj_wiersz(elem, mapowanie)
    assert out["nazwa_jednostki"] == "Katedra X"
    assert out["nazwisko"] == "Kowalski"
    assert "kolumna_smieciowa" not in out
    assert "jedn_org" not in out
    # klucze lokalizacyjne zachowane
    assert out["__xls_loc_sheet__"] == 0
    assert out["__xls_loc_row__"] == 7


@pytest.mark.django_db
def test_dopasuj_profil_pokrycie_ponad_90pct():
    ProfilMapowania.objects.create(
        nazwa="P",
        mapowanie={
            "nazwisko": "nazwisko",
            "imię": "imię",
            "jedn_org": "nazwa_jednostki",
        },
    )
    # nagłówki pokrywają się w 100% z kluczami profilu
    p = dopasuj_profil(["nazwisko", "imię", "jedn_org"])
    assert p is not None and p.nazwa == "P"


@pytest.mark.django_db
def test_dopasuj_profil_brak_gdy_niskie_pokrycie():
    ProfilMapowania.objects.create(
        nazwa="P",
        mapowanie={"a": "nazwisko", "b": "imię", "c": "nazwa_jednostki"},
    )
    assert dopasuj_profil(["zupełnie", "inne", "naglowki", "xyz"]) is None
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -k "remapuj or profil" -v`
Expected: FAIL (`ImportError: cannot import name 'remapuj_wiersz'`).

- [ ] **Step 3: Implementuj remap + dopasuj_profil**

Dopisz do `src/import_pracownikow/mapping.py`:

```python
# Klucze lokalizacyjne przechodzą przez remap bez zmian (kontrakt sortowania).
_KLUCZE_LOKALIZACJI = ("__xls_loc_sheet__", "__xls_loc_row__")


def remapuj_wiersz(elem, mapowanie):
    """Przepisuje klucze wiersza pliku na kanoniczne pola wg ``mapowanie``.
    Kolumny zmapowane na ``POLE_POMIN`` (lub bez wpisu) są pomijane. Klucze
    lokalizacyjne (``__xls_loc_*``) przechodzą bez zmian."""
    out = {}
    for klucz, wartosc in elem.items():
        if klucz in _KLUCZE_LOKALIZACJI:
            out[klucz] = wartosc
            continue
        cel = mapowanie.get(klucz, POLE_POMIN)
        if cel != POLE_POMIN:
            out[cel] = wartosc
    return out


def dopasuj_profil(naglowki):
    """Zwraca ``ProfilMapowania``, którego zbiór kluczy mapowania pokrywa
    ≥90% znormalizowanych nagłówków pliku (najlepsze pokrycie), albo ``None``.
    Import lokalny — moduł ``mapping`` bywa ładowany bez potrzeby ORM."""
    from import_pracownikow.models import ProfilMapowania

    zbior_naglowkow = set(naglowki)
    if not zbior_naglowkow:
        return None

    najlepszy = None
    najlepsze_pokrycie = 0.0
    for profil in ProfilMapowania.objects.all():
        klucze = set(profil.mapowanie.keys())
        if not klucze:
            continue
        pokrycie = len(zbior_naglowkow & klucze) / len(zbior_naglowkow)
        if pokrycie >= 0.9 and pokrycie > najlepsze_pokrycie:
            najlepszy = profil
            najlepsze_pokrycie = pokrycie
    return najlepszy
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -v`
Expected: PASS (8 łącznie).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/mapping.py src/import_pracownikow/tests/test_mapping.py
git commit -m "feat(import_pracownikow): remapowanie wiersza + dopasowanie profilu (Faza 2 T3)"
```

---

### Task 4: Pola nie-identyfikacyjne opcjonalne + helper nagłówki/próbka

Pliki z brakami kolumn: pola poza identyfikacją i jednostką stają się opcjonalne
w formularzach walidacji. Plus helper na modelu do synchronicznego podglądu
nagłówków + próbki dla ekranu mapowania.

**Files:**
- Modify: `src/import_pracownikow/models.py` (AutorForm, JednostkaForm — obie
  klasy Form żyją w `models.py`; helper; guardy integracji)
- Modify: `src/import_pracownikow/pipeline/analyze.py` (kompensacja guardu w
  `zmiany_potrzebne` — patrz Step 3)
- Test: `src/import_pracownikow/tests/test_models/test_mapowanie_model.py`
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze.py` (regresja
  odroczonego create przy istniejącym AJ)

**Interfaces:**
- Consumes: `otworz_zrodlo` (Faza 1).
- Produces:
  - `AutorForm` — `stanowisko`, `grupa_pracownicza`, `data_zatrudnienia`,
    `wymiar_etatu` mają `required=False` (były wymagane). `nazwisko`, `imię`
    zostają wymagane. `JednostkaForm.wydział` → `required=False`
    (`nazwa_jednostki` wymagane).
  - Guardy `is not None` w `_check_autor_jednostka_needs_update` /
    `_integrate_autor_jednostka` + kompensacja `zmiany_potrzebne = bool(diff) or
    check_if_integration_needed()` w `analyze._przetworz_wiersz`.
  - `ImportPracownikow.naglowki_i_probka(limit=10) -> tuple[list[str],
    list[dict]]` — znormalizowane nagłówki (klucze bez `__xls_loc_*`) i do
    `limit` wierszy próbki.

- [ ] **Step 1: Napisz failing test**

Dopisz do `src/import_pracownikow/tests/test_models/test_mapowanie_model.py`
(import `SimpleUploadedFile` dodaj do bloku importów NA GÓRZE pliku):

```python
from django.core.files.uploadedfile import SimpleUploadedFile

from import_pracownikow.models import AutorForm, JednostkaForm


def test_autorform_pola_nieidentyfikacyjne_opcjonalne():
    f = AutorForm()
    assert f.fields["nazwisko"].required is True
    assert f.fields["imię"].required is True
    for pole in ["stanowisko", "grupa_pracownicza", "data_zatrudnienia",
                 "wymiar_etatu"]:
        assert f.fields[pole].required is False, pole


def test_jednostkaform_wydzial_opcjonalny():
    f = JednostkaForm()
    assert f.fields["nazwa_jednostki"].required is True
    assert f.fields["wydział"].required is False


@pytest.mark.django_db
def test_naglowki_i_probka(admin_user):
    csv = (
        "Nazwisko;Imię;Nazwa jednostki\n"
        "Kowalski;Jan;Katedra\nNowak;Ewa;Zakład\n"
    ).encode("utf-8")
    imp = ImportPracownikow(owner=admin_user)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()
    naglowki, probka = imp.naglowki_i_probka(limit=10)
    assert "nazwisko" in naglowki and "nazwa_jednostki" in naglowki
    assert "__xls_loc_row__" not in naglowki  # klucze lokalizacyjne odfiltrowane
    assert len(probka) == 2


@pytest.mark.django_db
def test_brak_stanowiska_nie_kasuje_funkcji_przy_integracji():
    # KRYTYCZNE: plik BEZ kolumny stanowisko (funkcja_autora=None na wierszu)
    # NIE może skasować istniejącej aj.funkcja na None podczas integracji.
    from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora, Jednostka

    funkcja = baker.make(Funkcja_Autora)
    jednostka = baker.make(Jednostka)
    autor = baker.make(Autor)
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, funkcja=funkcja
    )
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        funkcja_autora=None,  # brak stanowiska w pliku
        grupa_pracownicza=None,
        wymiar_etatu=None,
        podstawowe_miejsce_pracy=None,
        dane_znormalizowane={},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    # ani check, ani integracja nie ruszają funkcji gdy wiersz jej nie ma
    dane = row.dane_bardziej_znormalizowane
    assert row._check_autor_jednostka_needs_update(dane) is False
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.funkcja_id == funkcja.pk  # NIE skasowane
```

(Import `ImportPracownikowRow` dodaj do bloku importów na górze pliku.)

Dodatkowo — regresja odroczonego create (F1) — do
`src/import_pracownikow/tests/test_pipeline/test_analyze.py` (reużywa `_wiersz`
i `patch(...analyze.otworz_zrodlo)` jak istniejące testy):

```python
@pytest.mark.django_db
def test_odroczony_create_przy_istniejacym_aj_wymaga_zmian(dwa_autory_z_jednostka):
    # plik MA stanowisko nieistniejące w bazie (odroczony create) + AJ istnieje
    # → wiersz MUSI mieć zmiany_potrzebne=True (bool(diff)), inaczej integracja
    # go pominie i funkcja nigdy nie powstanie (guard is-not-None wyzerował check)
    autor, jednostka = dwa_autory_z_jednostka
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [
                _wiersz(
                    nazwisko=autor.nazwisko,
                    imię=autor.imiona,
                    nazwa_jednostki=jednostka.nazwa,
                    stanowisko="NIEISTNIEJACE_STANOWISKO_XYZ",
                )
            ]
        )
        analizuj(imp, MockProgress(imp))
    row = imp.importpracownikowrow_set.get()
    assert "funkcja_autora" in row.diff_do_utworzenia
    assert row.zmiany_potrzebne is True
```

(Uwaga: `import pytest` już jest na górze pliku z Task 1 — nie duplikuj.)

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_mapowanie_model.py -v`
Expected: FAIL (pola wymagane / brak `naglowki_i_probka`).

- [ ] **Step 3: Zmień formularze + dodaj helper**

W `src/import_pracownikow/models.py`, w `AutorForm`, dodaj `required=False` do
czterech pól (zmień istniejące definicje):

```python
    stanowisko = forms.CharField(max_length=200, required=False)
    grupa_pracownicza = forms.CharField(max_length=200, required=False)
    data_zatrudnienia = ExcelDateField(required=False)
    wymiar_etatu = forms.CharField(max_length=200, required=False)
```

W `JednostkaForm` zmień `wydział`:

```python
    wydział = forms.CharField(max_length=500, required=False)
```

W klasie `ImportPracownikow` dodaj metodę (obok `run`/`on_restart`):

```python
    def naglowki_i_probka(self, limit=10):
        """Synchronicznie (bez liveops) czyta znormalizowane nagłówki i do
        ``limit`` wierszy próbki — na ekran mapowania. Nagłówki = klucze
        wiersza bez kluczy lokalizacyjnych. Używa ``TRY_NAMES``/``MIN_POINTS``
        z ``mapping`` (rozpoznaje przemianowane kolumny — patrz T2). Może rzucić
        ``HeaderNotFoundException`` (plik bez rozpoznawalnego nagłówka) — widok
        (T8) łapie to i pokazuje komunikat, nie 500."""
        from import_common.sources import otworz_zrodlo
        from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES

        zrodlo = otworz_zrodlo(
            self.plik_xls.path, try_names=TRY_NAMES, min_points=MIN_POINTS
        )
        probka = []
        naglowki = []
        for i, wiersz in enumerate(zrodlo.data()):
            if i == 0:
                naglowki = [
                    k
                    for k in wiersz.keys()
                    if k not in ("__xls_loc_sheet__", "__xls_loc_row__")
                ]
            if i >= limit:
                break
            probka.append(wiersz)
        return naglowki, probka
```

**KRYTYCZNE — guardy integracji (inaczej opcjonalne pola KASUJĄ dane).** Gdy
plik nie ma kolumny stanowisko/grupa/wymiar/podst. miejsce pracy, wiersz ma
`funkcja_autora=None` itd. Obecne `_check_autor_jednostka_needs_update` i
`_integrate_autor_jednostka` (`models.py`) porównują/nadpisują te pola
**bezwarunkowo** → integracja skasowałaby istniejące `aj.funkcja/grupa/wymiar`
na `None` i `podstawowe_miejsce_pracy` na `False`. Dodaj guard „porównuj/nadpisuj
tylko gdy wiersz ma wartość". W `ImportPracownikowRow._check_autor_jednostka_needs_update`
zamień listę `checks` na:

```python
        checks = [
            dane.get("data_zatrudnienia") is not None
            and aj.rozpoczal_prace != dane["data_zatrudnienia"],
            dane.get("data_końca_zatrudnienia") is not None
            and aj.zakonczyl_prace != dane["data_końca_zatrudnienia"],
            self.funkcja_autora is not None and aj.funkcja != self.funkcja_autora,
            self.grupa_pracownicza is not None
            and aj.grupa_pracownicza != self.grupa_pracownicza,
            self.wymiar_etatu is not None and aj.wymiar_etatu != self.wymiar_etatu,
            self.podstawowe_miejsce_pracy is not None
            and self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy,
        ]
```

W `_integrate_autor_jednostka` dodaj `self.X is not None` do warunków trzech
bloków (funkcja/grupa/wymiar) oraz podstawowego miejsca pracy:

```python
        if self.funkcja_autora is not None and aj.funkcja != self.funkcja_autora:
            aj.funkcja = self.funkcja_autora
            self.log_zmian["autor_jednostka"].append(
                f"funkcja na {self.funkcja_autora}"
            )

        if (
            self.grupa_pracownicza is not None
            and aj.grupa_pracownicza != self.grupa_pracownicza
        ):
            aj.grupa_pracownicza = self.grupa_pracownicza
            self.log_zmian["autor_jednostka"].append(
                f"grupa_pracownicza na {self.grupa_pracownicza}"
            )

        if self.wymiar_etatu is not None and aj.wymiar_etatu != self.wymiar_etatu:
            aj.wymiar_etatu = self.wymiar_etatu
            self.log_zmian["autor_jednostka"].append(
                f"wymiar_etatu na {self.wymiar_etatu}"
            )

        if (
            self.podstawowe_miejsce_pracy is not None
            and self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy
        ):
```

(pozostaw wewnętrzną logikę `if not self.podstawowe_miejsce_pracy: … else: …`
bez zmian — tylko dodaj zewnętrzny guard `is not None`).

**KRYTYCZNE — kompensacja guardu w analizie (inaczej odroczone create'y giną).**
Guard `is not None` sprawia, że wiersz z odroczonym create'em słownika (plik MA
stanowisko, ale `Funkcja_Autora` jeszcze nie istnieje → `funkcja_autora=None`,
wartość w `diff_do_utworzenia`) daje `check_if_integration_needed()==False` →
`zmiany_potrzebne=False` → `integruj` **pomija** wiersz → funkcja nigdy nie
powstaje. W `src/import_pracownikow/pipeline/analyze.py`, w `_przetworz_wiersz`,
zmień gałąź `aj is not None`:

```python
    if aj is not None:
        row.zmiany_potrzebne = row.check_if_integration_needed()
    else:
        row.zmiany_potrzebne = True
```

na:

```python
    if aj is not None:
        # bool(diff): wiersz z odroczonym create'em słownika (stanowisko/grupa/
        # wymiar nieistniejące w bazie) MUSI trafić do integracji, nawet gdy
        # guard is-not-None wyzerował check (funkcja_autora=None w analizie).
        row.zmiany_potrzebne = bool(diff) or row.check_if_integration_needed()
    else:
        row.zmiany_potrzebne = True
```

(NIE wpychaj `bool(diff)` do samego `check_if_integration_needed` — jest reużyty
po materializacji w `integrate._integruj_wiersz` i zmieniłoby to semantykę
`pominiety_bo_nieaktualny`.)

- [ ] **Step 4: Uruchom testy — zielone (+ regresja analizy Fazy 0/1)**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_mapowanie_model.py src/import_pracownikow/tests/test_pipeline/ -v`
Expected: PASS. **Uwaga:** opcjonalne pola nie mogą zepsuć istniejących testów
analizy (plik wzorcowy ma komplet kolumn, więc walidacja przechodzi jak dotąd).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/tests/test_models/test_mapowanie_model.py
git commit -m "feat(import_pracownikow): pola nie-identyfikacyjne opcjonalne + naglowki_i_probka (Faza 2 T4)"
```

---

### Task 5: Analiza remapuje klucze wg `mapowanie_kolumn`

`analizuj()` przed walidacją formularzem przepisuje klucze wiersza wg
`parent.mapowanie_kolumn`. Puste mapowanie (stare rekordy / brak) = brak remapu
(zachowanie Fazy 1 — klucze pliku już są kanoniczne w plikach wzorcowych).

**Files:**
- Modify: `src/import_pracownikow/pipeline/analyze.py`
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze_mapowanie.py`

**Interfaces:**
- Consumes: `remapuj_wiersz` (Task 3), `normalizuj_wartosci_wiersza` (Faza 1).
- Produces: `analizuj()` stosuje remap gdy `mapowanie_kolumn` niepuste.

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_analyze_mapowanie.py`:

```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.testing import MockProgress

from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj


@pytest.mark.django_db
def test_analiza_z_mapowaniem_inaczej_nazwanych_kolumn(
    admin_user, dwa_autory_z_jednostka
):
    autor, jednostka = dwa_autory_z_jednostka
    # plik z NIESTANDARDOWYMI nazwami kolumn — bez mapowania nie zadziała
    csv = (
        f"Nazwisko;Imie;Jedn org\n"
        f"{autor.nazwisko};{autor.imiona};{jednostka.nazwa}\n"
    ).encode("utf-8")
    imp = ImportPracownikow(
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZMAPOWANY,
        mapowanie_kolumn={
            "nazwisko": "nazwisko",
            "imie": "imię",
            "jedn_org": "nazwa_jednostki",
        },
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    analizuj(imp, MockProgress(imp))

    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.jednostka_id == jednostka.pk


@pytest.mark.django_db
def test_analiza_puste_mapowanie_zachowuje_zachowanie_fazy1(
    admin_user, dwa_autory_z_jednostka
):
    # plik ze standardowymi nazwami + puste mapowanie → działa jak w Fazie 1
    autor, jednostka = dwa_autory_z_jednostka
    csv = (
        "Nazwisko;Imię;Nazwa jednostki\n"
        f"{autor.nazwisko};{autor.imiona};{jednostka.nazwa}\n"
    ).encode("utf-8")
    imp = ImportPracownikow(
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZMAPOWANY,
        mapowanie_kolumn={},
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    analizuj(imp, MockProgress(imp))
    imp.refresh_from_db()
    assert imp.importpracownikowrow_set.get().autor_id == autor.pk
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_mapowanie.py -v`
Expected: FAIL (pierwszy test — bez remapu klucz `imie`/`jedn_org` nie trafi
w formularz → walidacja/matchowanie padnie).

- [ ] **Step 3: Dodaj remap do `analizuj()`**

W `src/import_pracownikow/pipeline/analyze.py` dodaj import (po bloku
`import_pracownikow.parsers.wartosci`):

```python
from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES, remapuj_wiersz
```

W `analizuj()` zmień otwarcie źródła (musi użyć TYCH SAMYCH `try_names` co ekran
mapowania — inaczej ekran przyjmie plik z przemianowanymi kolumnami, którego
analiza potem nie znajdzie nagłówka):

```python
    zrodlo = otworz_zrodlo(parent.plik_xls.path)
```

na:

```python
    zrodlo = otworz_zrodlo(
        parent.plik_xls.path, try_names=TRY_NAMES, min_points=MIN_POINTS
    )
```

oraz pętlę:

```python
    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        _przetworz_wiersz(parent, elem)
```

na (remap wg mapowania, gdy niepuste):

```python
    mapowanie = parent.mapowanie_kolumn or {}
    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        if mapowanie:
            elem = remapuj_wiersz(elem, mapowanie)
        _przetworz_wiersz(parent, elem)
```

**Uwaga:** `_przetworz_wiersz` już robi `dane_z_xls=elem` — po remapie `elem` to
przepisany dict (klucze kanoniczne). To akceptowalne: audyt pokazuje dane po
mapowaniu (surowe wartości, kanoniczne klucze). Surowe klucze pliku i tak są w
`parent.mapowanie_kolumn` (snapshot „czego użyto").

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/ -v`
Expected: PASS (nowe 2 + regresja Fazy 0/1).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze_mapowanie.py
git commit -m "feat(import_pracownikow): analiza remapuje klucze wg mapowanie_kolumn (Faza 2 T5)"
```

---

### Task 6: Dynamiczny `MapowanieForm` + zapis profilu

**Files:**
- Modify: `src/import_pracownikow/forms.py`
- Test: `src/import_pracownikow/tests/test_views_mapowanie.py` (część form)

**Interfaces:**
- Consumes: `POLA_DOCELOWE`, `POLE_POMIN`, `zaproponuj_mapowanie`,
  `waliduj_mapowanie` (mapping.py).
- Produces:
  - `MapowanieForm(naglowki, *args, initial_mapowanie=None, **kwargs)` — dla
    każdego nagłówka pole `ChoiceField` (choices = POLA_DOCELOWE + „pomiń"),
    prefill z `initial_mapowanie`. Pola: `kol__<naglowek>`. Dodatkowo
    `zapisz_profil` (BooleanField) + `nazwa_profilu` (CharField, required=False).
  - `MapowanieForm.mapowanie() -> dict` — `{naglowek: pole}` z cleaned_data.
  - `MapowanieForm.clean()` — woła `waliduj_mapowanie`, podpina błędy.

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_views_mapowanie.py` (BEZ `import
pytest` — testy T6 to czyste funkcje bez markerów; `import pytest` dokłada T8,
gdzie są `@pytest.mark.django_db`. Inaczej ruff F401 na commicie T6):

```python
from import_pracownikow.forms import MapowanieForm
from import_pracownikow.mapping import POLE_POMIN


def _dane(naglowki, mapowanie, zapisz=False, nazwa=""):
    d = {f"kol__{h}": mapowanie.get(h, POLE_POMIN) for h in naglowki}
    d["zapisz_profil"] = zapisz
    d["nazwa_profilu"] = nazwa
    return d


def test_mapowanieform_buduje_pola_z_naglowkow():
    f = MapowanieForm(naglowki=["nazwisko", "imię", "jedn_org"])
    assert "kol__nazwisko" in f.fields
    assert "kol__jedn_org" in f.fields
    # auto-propozycja jako initial
    assert f.fields["kol__jedn_org"].initial == "nazwa_jednostki"


def test_mapowanieform_valid_zwraca_mapowanie():
    naglowki = ["nazwisko", "imię", "jedn_org"]
    f = MapowanieForm(
        naglowki=naglowki,
        data=_dane(
            naglowki,
            {"nazwisko": "nazwisko", "imię": "imię", "jedn_org": "nazwa_jednostki"},
        ),
    )
    assert f.is_valid(), f.errors
    assert f.mapowanie() == {
        "nazwisko": "nazwisko",
        "imię": "imię",
        "jedn_org": "nazwa_jednostki",
    }


def test_mapowanieform_invalid_bez_jednostki():
    naglowki = ["nazwisko", "imię"]
    f = MapowanieForm(
        naglowki=naglowki,
        data=_dane(naglowki, {"nazwisko": "nazwisko", "imię": "imię"}),
    )
    assert not f.is_valid()
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_mapowanie.py -v`
Expected: FAIL (`ImportError: cannot import name 'MapowanieForm'`).

- [ ] **Step 3: Implementuj `MapowanieForm`**

W `src/import_pracownikow/forms.py` dodaj (importy u góry):

```python
from import_pracownikow.mapping import (
    POLA_DOCELOWE,
    POLE_POMIN,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)
```

Klasa (po `NowyImportForm`):

```python
class MapowanieForm(forms.Form):
    """Dynamiczny formularz mapowania: jedno pole ``ChoiceField`` na każdy
    nagłówek pliku (klucz ``kol__<naglowek>``), prefill z auto-propozycji
    lub przekazanego ``initial_mapowanie`` (np. z profilu)."""

    zapisz_profil = forms.BooleanField(
        required=False, label="Zapisz to mapowanie jako profil"
    )
    nazwa_profilu = forms.CharField(
        required=False, max_length=200, label="Nazwa profilu"
    )

    def __init__(self, *args, naglowki=None, initial_mapowanie=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.naglowki = naglowki or []
        # merge: auto-propozycja jako baza, profil (jeśli jest) nadpisuje —
        # dzięki temu nagłówki spoza profilu i tak dostają synonim, nie „pomiń".
        propozycja = {
            **zaproponuj_mapowanie(self.naglowki),
            **(initial_mapowanie or {}),
        }
        wybory = [(POLE_POMIN, "— pomiń —")] + [
            (k, etykieta) for k, etykieta in POLA_DOCELOWE
        ]
        for h in self.naglowki:
            self.fields[f"kol__{h}"] = forms.ChoiceField(
                choices=wybory,
                required=True,
                label=h,
                initial=propozycja.get(h, POLE_POMIN),
            )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit("submit", "Zapisz mapowanie i analizuj", css_class="button")
        )

    def mapowanie(self):
        """``{naglowek: pole_docelowe}`` z oczyszczonych danych."""
        return {
            h: self.cleaned_data[f"kol__{h}"]
            for h in self.naglowki
            if f"kol__{h}" in self.cleaned_data
        }

    def clean(self):
        cleaned = super().clean()
        bledy = waliduj_mapowanie(self.mapowanie())
        for e in bledy:
            self.add_error(None, e)
        if cleaned.get("zapisz_profil") and not cleaned.get("nazwa_profilu"):
            self.add_error(
                "nazwa_profilu", "Podaj nazwę profilu, aby go zapisać."
            )
        return cleaned
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_mapowanie.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/forms.py \
  src/import_pracownikow/tests/test_views_mapowanie.py
git commit -m "feat(import_pracownikow): dynamiczny MapowanieForm + zapis profilu (Faza 2 T6)"
```

---

### Task 7: Przełączenie maszyny stanów — `run()`, `on_restart`, `form_valid`

Dyspozytor przestaje odpalać analizę dla `utworzony` (teraz to ekran mapowania);
analizę odpala `zmapowany`. Upload zapisuje bez `enqueue` i przekierowuje na
ekran mapowania. `on_restart` kasuje wiersze przy `zmapowany`.

**Files:**
- Modify: `src/import_pracownikow/models.py` (`run`, `on_restart`)
- Modify: `src/import_pracownikow/views.py` (`NowyImportView`, `RestartAnalizaView`)
- Test: `src/import_pracownikow/tests/test_models/test_mapowanie_model.py`

**Interfaces:**
- Consumes: `STAN_ZMAPOWANY` (Task 1), `analizuj` (Faza 0/1).
- Produces: `run()` — `zmapowany`→analiza, `zatwierdzony`→integracja, reszta
  (w tym `utworzony`) no-op z logiem. `on_restart()` — kasuje wiersze gdy
  `stan in (utworzony, zmapowany)`. `RestartAnalizaView` — cofa do `zmapowany`.
  (`NowyImportView.form_valid` — w T8, razem z URL `mapowanie`.)

- [ ] **Step 1: Napisz failing test**

Dopisz do `src/import_pracownikow/tests/test_models/test_mapowanie_model.py`:

```python
from liveops.testing import MockProgress


@pytest.mark.django_db
def test_run_utworzony_nie_odpala_analizy(admin_user):
    # po Fazie 2: utworzony = czeka na mapowanie, run() jest no-op
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    imp.run(MockProgress(imp))  # nie może rzucić ani nic policzyć
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_UTWORZONY
    assert imp.importpracownikowrow_set.count() == 0


@pytest.mark.django_db
def test_on_restart_kasuje_wiersze_przy_zmapowany(admin_user):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    baker.make("import_pracownikow.ImportPracownikowRow", parent=imp)
    imp.on_restart()
    assert imp.importpracownikowrow_set.count() == 0
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_mapowanie_model.py -k "run_utworzony or on_restart" -v`
Expected: FAIL (obecnie `utworzony`→analiza, `on_restart` kasuje tylko przy
`utworzony`).

- [ ] **Step 3: Zmień `run()` i `on_restart()`**

W `src/import_pracownikow/models.py` zamień `run()`:

```python
    def run(self, p):
        if self.stan == self.STAN_ZMAPOWANY:
            from import_pracownikow.pipeline.analyze import analizuj

            analizuj(self, p)
        elif self.stan == self.STAN_ZATWIERDZONY:
            from import_pracownikow.pipeline.integrate import integruj

            integruj(self, p)
        else:
            p.log(f"run() w nieoczekiwanym stanie: {self.stan!r} — pomijam")
```

i `on_restart()`:

```python
    def on_restart(self):
        # kasujemy wiersze przy (ponownej) analizie: świeży upload czeka w
        # utworzony (bez wierszy), ponowna analiza cofa do zmapowany.
        if self.stan in (self.STAN_UTWORZONY, self.STAN_ZMAPOWANY):
            self.importpracownikowrow_set.all().delete()
```

- [ ] **Step 4: `RestartAnalizaView` cofa do `zmapowany`**

W `src/import_pracownikow/views.py`, w `RestartAnalizaView.post` zamień
`STAN_UTWORZONY` na `STAN_ZMAPOWANY`:

```python
        obj.stan = ImportPracownikow.STAN_ZMAPOWANY
```

(oraz docstring: „Cofa import do stanu ``zmapowany`` i uruchamia analizę od
nowa.")

**Uwaga:** `NowyImportView.form_valid` (bez enqueue, redirect na ekran
mapowania) wchodzi **dopiero w T8** — razem z URL-em `mapowanie` i widokiem,
żeby nie było commita z `NoReverseMatch`. Między T7 a T8 upload używa
domyślnego `form_valid` z `CreateLiveOperationView` (enqueue → `run()` w stanie
`utworzony` → no-op z logiem → operacja kończy się „pusto"). To zdegradowany,
ale nie-crashujący stan pośredni.

- [ ] **Step 5: Zaktualizuj testy Fazy 0/1 (dyspozytor odpala teraz `zmapowany`)**

Przełączenie `run()` (utworzony przestaje odpalać analizę) łamie fixtury/testy,
które robiły `stan=STAN_UTWORZONY; run(...)`. Zaktualizuj:

- `src/import_pracownikow/tests/conftest.py` (`import_pracownikow_performed`,
  ~linia 80): `import_pracownikow.stan = import_pracownikow.STAN_UTWORZONY` →
  `... .STAN_ZMAPOWANY`.
- `src/import_pracownikow/tests/test_models/test_models.py` (`_pelny_przebieg`,
  ~linia 15): `imp.stan = ImportPracownikow.STAN_UTWORZONY` → `... .STAN_ZMAPOWANY`.
- `src/import_pracownikow/tests/test_models/test_liveops_model.py`
  (`test_run_dispatch_po_stanie`, ~linia 29):
  `baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)` →
  `... stan=ImportPracownikow.STAN_ZMAPOWANY)` (pierwsze `run(p=object())` ma
  odpalić „analiza"). NIE ruszaj innych asercji tego testu.
- `src/import_pracownikow/tests/test_views_liveops.py`
  (`test_restart_analiza_cofa_stan_i_kasuje_wiersze`, ~linia 71):
  `assert imp.stan == ImportPracownikow.STAN_UTWORZONY` → `... .STAN_ZMAPOWANY`
  (asercja `count()==0` zostaje — `on_restart` kasuje wiersze także przy
  `zmapowany`).

- [ ] **Step 6: Uruchom testy — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/ src/import_pracownikow/tests/test_views_liveops.py -v`
Expected: PASS (nowe testy T7 + zaktualizowane Fazy 0/1).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/views.py \
  src/import_pracownikow/tests/conftest.py \
  src/import_pracownikow/tests/test_models/test_models.py \
  src/import_pracownikow/tests/test_models/test_liveops_model.py \
  src/import_pracownikow/tests/test_views_liveops.py
git commit -m "feat(import_pracownikow): przełącz maszynę stanów — analiza po zmapowany (Faza 2 T7)"
```

---

### Task 8: `MapowanieView` + URL + template + zapis profilu → enqueue

Ekran mapowania: GET pokazuje `MapowanieForm` (prefill z profilu lub
auto-propozycji) + próbkę; POST zapisuje `mapowanie_kolumn`, ewentualny profil,
przechodzi w `zmapowany` i kolejkuje analizę (redirect na stronę live).

**Files:**
- Modify: `src/import_pracownikow/views.py`, `urls.py`
- Create: `src/import_pracownikow/templates/import_pracownikow/mapowanie.html`
- Modify: `src/import_pracownikow/templates/import_pracownikow/importpracownikow_list.html`
  (link „dokończ mapowanie" dla `stan == "utworzony"` — F5)
- Test: `src/import_pracownikow/tests/test_views_mapowanie.py`

**Interfaces:**
- Consumes: `MapowanieForm` (Task 6), `naglowki_i_probka` (Task 4),
  `dopasuj_profil` (Task 3), `ProfilMapowania` (Task 1), `STAN_ZMAPOWANY`.
- Produces: `MapowanieView` (GET/POST), URL name `mapowanie`.

- [ ] **Step 1: Napisz failing testy (widok)**

Dopisz do `src/import_pracownikow/tests/test_views_mapowanie.py`:

Dodaj do `test_views_mapowanie.py` (importy do bloku NA GÓRZE pliku — dołącz
`import pytest` i resztę do istniejących importów z T6):

```python
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from import_pracownikow.models import ImportPracownikow, ProfilMapowania

# W testach LIVEOPS.RUNNER="eager" (settings/test.py) — enqueue() wykonuje run()
# SYNCHRONICZNIE. W testach jednostkowych widoku patchujemy run, żeby POST nie
# odpalał analizy (brak autora/jednostki w DB → wyjątek; poza tym testujemy
# zapis mapowania, nie analizę).
_PATCH_RUN = patch.object(ImportPracownikow, "run", lambda self, p: None)


def _upload_csv(admin_user):
    csv = ("Nazwisko;Imie;Jedn org\nKowalski;Jan;Katedra\n").encode("utf-8")
    imp = ImportPracownikow(
        owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()
    return imp


@pytest.mark.django_db
def test_mapowanie_get_pokazuje_kolumny(admin_client, admin_user):
    imp = _upload_csv(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"kol__nazwisko" in resp.content
    assert b"kol__jedn_org" in resp.content


@pytest.mark.django_db
def test_mapowanie_post_zapisuje_i_przechodzi_w_zmapowany(
    admin_client, admin_user
):
    imp = _upload_csv(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    data = {
        "kol__nazwisko": "nazwisko",
        "kol__imie": "imię",
        "kol__jedn_org": "nazwa_jednostki",
        "zapisz_profil": False,
        "nazwa_profilu": "",
    }
    with _PATCH_RUN:
        resp = admin_client.post(url, data)
    assert resp.status_code == 302  # redirect na stronę live
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZMAPOWANY
    assert imp.mapowanie_kolumn["jedn_org"] == "nazwa_jednostki"


@pytest.mark.django_db
def test_mapowanie_post_zapisuje_profil(admin_client, admin_user):
    imp = _upload_csv(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    data = {
        "kol__nazwisko": "nazwisko",
        "kol__imie": "imię",
        "kol__jedn_org": "nazwa_jednostki",
        "zapisz_profil": True,
        "nazwa_profilu": "Mój profil",
    }
    with _PATCH_RUN:
        admin_client.post(url, data)
    assert ProfilMapowania.objects.filter(nazwa="Mój profil").exists()


@pytest.mark.django_db
def test_mapowanie_post_na_zintegrowanym_nie_kasuje_wierszy(admin_client, admin_user):
    # gate stanu (F4): import zintegrowany nie jest mapowalny — POST NIE może
    # skasować wierszy-audytu (log_zmian) ani odpalić ponownej analizy
    imp = _upload_csv(admin_user)
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY
    imp.save(update_fields=["stan"])
    from model_bakery import baker

    baker.make("import_pracownikow.ImportPracownikowRow", parent=imp)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    with _PATCH_RUN:
        resp = admin_client.post(
            url,
            {
                "kol__nazwisko": "nazwisko",
                "kol__imie": "imię",
                "kol__jedn_org": "nazwa_jednostki",
                "zapisz_profil": False,
                "nazwa_profilu": "",
            },
        )
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY  # niezmieniony
    assert imp.importpracownikowrow_set.count() == 1  # audyt zachowany
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_mapowanie.py -k mapowanie_ -v`
Expected: FAIL (brak URL/widoku).

- [ ] **Step 3: `NowyImportView.form_valid` (bez enqueue) + `MapowanieView`**

W `src/import_pracownikow/views.py` dodaj importy:

```python
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.generic import FormView

from import_common.exceptions import HeaderNotFoundException
from import_pracownikow.forms import MapowanieForm
from import_pracownikow.mapping import dopasuj_profil
from import_pracownikow.models import ProfilMapowania
```

W `NowyImportView` dodaj `form_valid` (nadpisuje `CreateLiveOperationView`, żeby
NIE kolejkować — najpierw ekran mapowania):

```python
    def form_valid(self, form):
        # NIE enqueue — najpierw ekran mapowania (analiza dopiero po zmapowaniu).
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        self.object.stan = ImportPracownikow.STAN_UTWORZONY
        self.object.save()
        return HttpResponseRedirect(
            reverse("import_pracownikow:mapowanie", kwargs={"pk": self.object.pk})
        )
```

Klasa `MapowanieView`:

```python
# Stany, w których mapowanie jest dozwolone (przed commitem). NIE zmapowany na
# zintegrowanym — kasowanie wierszy zniszczyłoby audyt log_zmian (spec §4).
_STANY_MAPOWALNE = (
    ImportPracownikow.STAN_UTWORZONY,
    ImportPracownikow.STAN_ZMAPOWANY,
    ImportPracownikow.STAN_PRZEANALIZOWANY,
)

_POLA_RESET_LIVEOPS = [
    "finished_on",
    "started_on",
    "finished_successfully",
    "cancelled",
    "cancel_requested",
    "traceback",
    "result_context",
    "current_stage",
    "stage_states",
    "log",
    "percent",
    "log_seq",
]


class MapowanieView(GroupRequiredMixin, FormView):
    """Ekran mapowania kolumn. GET: auto-propozycja (lub profil) + próbka.
    POST: zapis mapowania + ewentualny profil → stan zmapowany → (re)enqueue."""

    group_required = GROUP_REQUIRED
    form_class = MapowanieForm
    template_name = "import_pracownikow/mapowanie.html"

    @cached_property
    def object(self):
        return get_object_or_404(
            ImportPracownikow, pk=self.kwargs["pk"], owner=self.request.user
        )

    def _przygotuj(self, request):
        """Wywoływane z get()/post() (PO kontroli dostępu GroupRequiredMixin,
        żeby nie robić I/O pliku dla anonimowego/bez-grupy usera). Zwraca
        ``HttpResponseRedirect`` (błąd) albo ``None`` (OK)."""
        if self.object.stan not in _STANY_MAPOWALNE:
            messages.error(
                request, "Tego importu nie można już mapować (zatwierdzony)."
            )
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        try:
            self._naglowki, self._probka = self.object.naglowki_i_probka()
        except HeaderNotFoundException:
            messages.error(
                request,
                "Nie rozpoznano wiersza nagłówka w pliku — sprawdź, czy plik "
                "zawiera kolumny takie jak nazwisko / imię / jednostka.",
            )
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        if not self._naglowki:
            messages.error(request, "Plik nie zawiera kolumn do zmapowania.")
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        return None

    def get(self, request, *args, **kwargs):
        return self._przygotuj(request) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._przygotuj(request) or super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["naglowki"] = self._naglowki
        profil = dopasuj_profil(self._naglowki)
        if profil is not None:
            kwargs["initial_mapowanie"] = profil.mapowanie
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.object
        ctx["probka_rows"] = [
            [w.get(h, "") for h in self._naglowki] for w in self._probka
        ]
        return ctx

    def form_valid(self, form):
        obj = self.object
        obj.mapowanie_kolumn = form.mapowanie()
        obj.stan = ImportPracownikow.STAN_ZMAPOWANY
        # on_restart() kasuje wiersze podglądu (stan==zmapowany) — inaczej
        # ponowna analiza by je zduplikowała.
        obj.on_restart()
        # Reset pól operacji liveops (jak RestartView.post) — inaczej po
        # anulowanym/zakończonym przebiegu enqueue rusza z brudnym stanem
        # (cancel_requested=True → natychmiastowe „cancelled").
        obj.finished_on = None
        obj.started_on = None
        obj.finished_successfully = False
        obj.cancelled = False
        obj.cancel_requested = False
        obj.traceback = None
        obj.result_context = None
        obj.current_stage = -1
        obj.stage_states = {}
        obj.log = []
        obj.percent = 0
        obj.log_seq = 0
        obj.save(update_fields=["mapowanie_kolumn", "stan"] + _POLA_RESET_LIVEOPS)

        if form.cleaned_data.get("zapisz_profil"):
            ProfilMapowania.objects.update_or_create(
                nazwa=form.cleaned_data["nazwa_profilu"],
                defaults={
                    "mapowanie": obj.mapowanie_kolumn,
                    "utworzony_przez": self.request.user,
                    "ostatnio_uzyty": timezone.now(),
                },
            )

        obj.enqueue()
        return HttpResponseRedirect(obj.get_absolute_url())
```

**Uwaga:** `_przygotuj` (fetch obiektu + I/O pliku) woła się z `get()`/`post()`,
czyli PO `GroupRequiredMixin.dispatch` (kontrola loginu/grupy) — anonimowy/bez
grupy user nie dotyka pliku ani `owner`-lookupu. Wynik nagłówków/próbki jest w
`self._naglowki`/`self._probka` (jedno I/O na request).

- [ ] **Step 4: Dodaj URL**

W `src/import_pracownikow/urls.py` dodaj (po `new/`):

```python
    path(
        "<uuid:pk>/mapowanie/",
        views.MapowanieView.as_view(),
        name="mapowanie",
    ),
```

- [ ] **Step 5: Template**

Utwórz `src/import_pracownikow/templates/import_pracownikow/mapowanie.html`
(wzorzec: `import_dyscyplin/import_dyscyplin_kolumny.html`). Nagłówek próbki z
`form.naglowki`, ciało z `probka_rows` (lista list, budowana w widoku).
**Komentarze `{# #}` jedno-liniowe** — każda linia własne `{# ... #}`:

```django
{% extends "base.html" %}
{% load crispy_forms_tags %}

{% block extratitle %}Import pracowników — mapowanie kolumn{% endblock %}

{% block content %}
    <h1>Zweryfikuj kolumny</h1>
    {# lewa strona = nazwy kolumn z pliku, prawa = docelowe pole systemowe #}
    <p>
        Dla każdej kolumny pliku wskaż pole systemowe, na które ma zostać
        odwzorowana (albo „pomiń"). Wymagane: nazwisko, imię, nazwa jednostki.
    </p>

    {% if probka_rows %}
        <h2>Próbka danych</h2>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        {% for h in form.naglowki %}<th>{{ h }}</th>{% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for kolumny in probka_rows %}
                        <tr>
                            {% for kom in kolumny %}<td>{{ kom }}</td>{% endfor %}
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    {% endif %}

    {% crispy form %}
{% endblock %}
```

**Link powrotu do mapowania (F5).** Import porzucony na ekranie mapowania
(`stan == "utworzony"`, nigdy nie enqueue'owany) jest inaczej nieosiągalny z UI.
W `src/import_pracownikow/templates/import_pracownikow/importpracownikow_list.html`
w pętli `{% for object in object_list %}` dodaj po linku `get_absolute_url`
(Foundation-Icons we froncie publicznym, komentarze `{# #}` jedno-liniowe):

```django
                {% if object.stan == "utworzony" %}
                    — <a href="{% url "import_pracownikow:mapowanie" pk=object.pk %}">
                        <i class="fi-arrow-right"></i> dokończ mapowanie kolumn
                    </a>
                {% endif %}
```

- [ ] **Step 6: Uruchom testy — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_mapowanie.py -v`
Expected: PASS (7: form + widok + gate stanu).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/templates/import_pracownikow/mapowanie.html \
  src/import_pracownikow/templates/import_pracownikow/importpracownikow_list.html \
  src/import_pracownikow/tests/test_views_mapowanie.py
git commit -m "feat(import_pracownikow): ekran mapowania kolumn + zapis profilu → enqueue (Faza 2 T8)"
```

---

### Task 9: E2E przez ekran + regresja + newsfragment

**Files:**
- Create: `src/import_pracownikow/tests/test_pipeline/test_faza2_e2e.py`
- Create: `src/bpp/newsfragments/import-pracownikow-mapowanie-kolumn.feature.rst`

**Interfaces:**
- Consumes: cały przepływ Fazy 2 (upload → mapowanie → analiza).

- [ ] **Step 1: Napisz test e2e**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_faza2_e2e.py`:

```python
"""E2E Fazy 2: upload pliku z NIESTANDARDOWYMI nazwami kolumn → ekran
mapowania (POST) → stan zmapowany → analiza (eager enqueue) → wiersze.

W testach LIVEOPS.RUNNER="eager" (settings/test.py), więc ``enqueue()`` w
``MapowanieView.form_valid`` wykonuje ``run()`` SYNCHRONICZNIE — analiza
odpala się w ramach POST-a, bez ręcznego ``run()``."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_e2e_upload_mapowanie_analiza(admin_client, admin_user, dwa_autory_z_jednostka):
    autor, jednostka = dwa_autory_z_jednostka
    csv = (
        f"Nazwisko;Imie;Jedn org\n{autor.nazwisko};{autor.imiona};{jednostka.nazwa}\n"
    ).encode("utf-8")
    imp = ImportPracownikow(
        owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    # ekran mapowania: POST z korektą (Imie→imię, Jedn org→nazwa_jednostki).
    # Pod eager runnerem enqueue() z form_valid od razu wykona analizę.
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {
            "kol__nazwisko": "nazwisko",
            "kol__imie": "imię",
            "kol__jedn_org": "nazwa_jednostki",
            "zapisz_profil": False,
            "nazwa_profilu": "",
        },
    )
    assert resp.status_code == 302
    imp.refresh_from_db()
    # analiza wykonana eager w ramach POST-a:
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.jednostka_id == jednostka.pk
```

- [ ] **Step 2: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_faza2_e2e.py -v`
Expected: PASS.

- [ ] **Step 3: Newsfragment**

Utwórz `src/bpp/newsfragments/import-pracownikow-mapowanie-kolumn.feature.rst`:

```rst
Import pracowników ma teraz ekran **mapowania kolumn**: pliki z inaczej
nazwanymi lub brakującymi kolumnami można dopasować do pól systemowego importu
(z auto-propozycją i zapisywalnymi profilami dla powtarzalnych plików).
```

- [ ] **Step 4: Pełna regresja Fazy 0+1+2**

Run: `uv run pytest src/import_pracownikow/ src/import_common/ -q`
Expected: PASS wszystko. Podaj liczbę passed/failed.

- [ ] **Step 5: Ruff + pinned format**

Run: `uv run pre-commit run ruff-format --files $(git diff --name-only $(git merge-base dev HEAD) | tr '\n' ' ')`
oraz `uv run ruff check src/import_pracownikow/`
Expected: czyste (dołącz zmiany formatera do commita). **Uwaga:** pinned
pre-commit ruff bywa surowszy niż `uv run ruff format` — używaj hooka.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/tests/test_pipeline/test_faza2_e2e.py \
  src/bpp/newsfragments/import-pracownikow-mapowanie-kolumn.feature.rst
git commit -m "test(import_pracownikow): e2e mapowanie + newsfragment (Faza 2 T9)"
```

---

## Self-Review (autor planu)

**Spec coverage (§6):**
- Auto-detekcja + ekran korekty + profile (D1 hybryda) → T2/T6/T8 ✅
- Słownik synonimów (kod, wersjonowany) → T2 `_SYNONIMY` ✅
- Pola obowiązkowe = identyfikacja + jednostka; reszta opcjonalna → T2 walidacja
  + T4 formularze ✅
- Snapshot `mapowanie_kolumn` + `ProfilMapowania` (auto-prefill ≥90%) → T1/T3/T8 ✅
- Przełączenie maszyny stanów (utworzony→ekran, zmapowany→analiza, custom
  form_valid bez enqueue, on_restart) → T7 ✅ (§4/§14)
- PESEL nieoferowany: nagłówki z `naglowki_i_probka` pochodzą z `data()` źródła,
  które już filtruje `DEFAULT_BANNED_NAMES` (Faza 1) → pesel nie dotrze do
  ekranu ✅

**Placeholder scan:** brak TBD/TODO; kod kompletny. (Template Task 8 zawiera
jawne rozwiązanie zamiast nieistniejącego filtra — `probka_rows` w widoku.)

**Type consistency:** `mapowanie_kolumn` to `{naglowek: pole}` wszędzie
(zaproponuj/waliduj/remapuj/MapowanieForm.mapowanie/dopasuj_profil). `POLE_POMIN`
spójny sentinel. `run()`/`on_restart` używają `STAN_ZMAPOWANY` z T1.

**Migracje/baseline:** jedna nowa migracja `0012`; baseline dopiero przy merge
(reguła CLAUDE.md).

**Świadome ograniczenia perf (v1):** `naglowki_i_probka` czyta plik przez
`otworz_zrodlo`→`load_workbook` (całe workbook w RAM) przy każdym GET/POST
ekranu; spec §4 sugeruje `read_only=True` + ~10 wierszy. Na wielo-MB plikach
kadrowych ekran będzie chwilę mulił — optymalizacja (read-only sniff) odłożona.
`ProfilMapowania.ostatnio_uzyty` ustawiany przy zapisie profilu, nie przy
`dopasuj_profil` (użyciu) — kosmetyka, do domknięcia gdy potrzebna telemetria.

**Recenzje (subagent Fable):** iter1 — 16 findingów, w tym 5 krytycznych:
(1) detekcja nagłówka wymagała 3 kanonicznych nazw → plik z przemianowanymi
kolumnami nie dochodził do ekranu — naprawione `TRY_NAMES`/`MIN_POINTS` w
`naglowki_i_probka` I `analizuj`; (2) przełączenie `run()` psuło testy Fazy 0/1
— T7 aktualizuje conftest/test_models/test_liveops_model/test_views_liveops;
(3) SyntaxError w f-stringu walidacji — naprawione; (4) opcjonalne pola
KASOWAŁY dane przy integracji (`aj.funkcja→None`) — dodane guardy `is not None`
w `_check`/`_integrate_autor_jednostka` + test regresyjny; (5) re-mapowanie
duplikowałoby wiersze — `form_valid` kasuje wiersze przed enqueue. Ważne:
eager runner w testach (patch `run`), obsługa `HeaderNotFoundException` w
widoku (nie 500), `FormHelper`+Submit, przeniesienie `form_valid` do T8
(unik `NoReverseMatch`). Wszystkie naniesione.

iter2 — zweryfikował poprawki iter1 na kodzie (poprawne) + 5 nowych: F1
[KRYT] guard `is not None` psuł integrację odroczonych create'ów →
kompensacja `zmiany_potrzebne = bool(diff) or check(...)` + test; F2 widok
robił I/O pliku przed kontrolą dostępu → `_przygotuj` z get()/post() (po
auth); F3 `enqueue` bez resetu pól liveops (cancel_requested → natychmiast
„cancelled") → pełny reset jak RestartView; F4 brak gate'u stanu → POST na
zintegrowanym kasował audyt → `_STANY_MAPOWALNE` + test; F5 brak drogi
powrotnej do mapowania → link w liście dla `utworzony`. Minory (E501/F401/
E402/synonim „Tytuł / Stopień"/File-Structure) naniesione. Wszystkie
naniesione.
