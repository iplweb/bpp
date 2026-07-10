# Import pracowników — Faza 3: parser sklejonej osoby + wskaźnik pewności + edycja inline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rozbić sklejoną komórkę „tytuł+imię+nazwisko" na składniki, policzyć
status pewności dopasowania autora (twardy/zgadywanie/wielu/brak) zamiast
twardego błędu wiersza i pozwolić userowi korygować rozbicie oraz wybierać
kandydata inline (HTMX) w podglądzie.

**Architecture:** Czysty rdzeń parsera (`parsers/osoba.py`, bez ORM, testowany
tabelarycznie z atrapami) rozbija sklejoną osobę; adapter (`parsers/leksykony.py`)
wstrzykuje realne słowniki tytułów/imion z bazy i callable `probuj_match`. Faza
analizy woła parser gdy zmapowano `osoba_sklejona`, a status pewności liczy WPROST
z `znajdz_kandydatow_autora` (czysta funkcja `pewnosc.oblicz_status_pewnosci`),
NIE z `matchuj_autora` (poza priorytetową ścieżką po ID). Statusy `brak`/`wielu`
przestają być błędem wiersza — wiersz zapisuje się bez autora, kandydaci lądują w
`ImportPracownikowRowKandydat`, a user rozstrzyga w podglądzie: wybór kandydata
(POST) i korekta rozbicia (HTMX POST) synchronicznie ponawiają match tego wiersza.

**Tech Stack:** Django, django-liveops, HTMX (unpkg 2.0.4, wzorzec
`importer_publikacji`), Foundation CSS (label + Foundation-Icons), pytest,
model_bakery, testcontainers.

## Global Constraints

- **Max 88 znaków/linia** (ruff); **zawsze `uv run`** dla poleceń Pythona.
- **NIE modyfikować istniejących migracji** `src/*/migrations/`. Faza 3 dodaje
  JEDNĄ nową migrację (`0013_confidence_kandydaci`), generowaną przez
  `uv run python src/manage.py makemigrations` — NIGDY ręcznie.
- **Baseline (`make baseline-update`) NIE na tym feature-branchu** — dopiero przy
  merge (reguła CLAUDE.md). W planie NIE ma kroku baseline.
- **Backward compat:** istniejące stany i przejścia Faz 0–2
  (`utworzony`/`zmapowany`/`przeanalizowany`/`zatwierdzony`/`zintegrowany`/
  `porzucony`) muszą działać. Wiersze są ulotne (kasowane przy re-analizie), więc
  nowe pola mają bezpieczne defaulty (`confidence` nullable, `korekta_uzytkownika`
  default dict, `wybrany_kandydat` nullable).
- **Bez `except: pass`** — wąski typ wyjątku + komentarz WHY.
- **Komentarze szablonów Django `{# #}` JEDNOLINIOWE** — KAŻDA linia własne
  `{# ... #}`. Wieloliniowy komentarz wycieka do HTML.
- **Ikony we froncie publicznym: Foundation-Icons** (`<i class="fi-...">`), NIE
  emoji (emoji tylko w django-adminie).
- **pytest, nie unittest**; funkcje bez klas; `@pytest.mark.django_db` gdy DB;
  `model_bakery.baker.make`. Parser = testy TABELARYCZNE (`@pytest.mark.parametrize`).
- **Testy przez testcontainers** (Docker daemon wymagany); pełna suita do 10 min.

## Decyzje architektoniczne (podjęte — NIE zmieniać)

1. **Dwa różne „confidence".** Parser (§7) zwraca `confidence: high|medium|low`
   (pewność ROZBICIA imienia) — zapisywany WEWNĄTRZ `dane_znormalizowane` (JSON),
   NIE kolumna. Status dopasowania AUTORA (§8): `twardy|zgadywanie|wielu|brak` —
   NOWA KOLUMNA `confidence` na `ImportPracownikowRow`.
2. **Priorytet ścieżki po ID.** Jeśli wiersz ma bpp_id/orcid/pbn_uuid/numer(system
   kadrowy)/pbn_id → ścieżka ID (istniejący `matchuj_autora`, który już przyjmuje
   te argumenty). Match po ID → `confidence=twardy`. Konflikt `bpp_id` z pliku ≠ pk
   zmatchowanego autora → TWARDY BŁĄD wiersza (`XLSMatchError`, jak dziś).
3. **Status z `znajdz_kandydatow_autora`, NIE z `matchuj_autora`** (poza ID).
   `oblicz_status_pewnosci` to CZYSTA funkcja w osobnym module
   `import_pracownikow/pewnosc.py` (osobny moduł, nie `mapping.py`: `mapping.py`
   dotyczy kolumn, nie autorów; a stałe `STATUS_*` muszą być importowalne przez
   model bez sięgania do warstwy mapowania). Jednostka/tytuł NIE wpływają na status
   ani `pewnosc` (są tylko tie-breakerami preselekcji w dropdownie `wielu`).
4. **`brak`/`wielu` NIE są już błędem wiersza.** `twardy`/`zgadywanie` →
   `row.autor = kandydaci[0].autor` (albo autor z ID). `wielu` → `row.autor=None`,
   zapis WSZYSTKICH kandydatów jako `ImportPracownikowRowKandydat`,
   `zmiany_potrzebne=False`. `brak` → `row.autor=None`, `zmiany_potrzebne=False`.
   ID-konflikt `bpp_id` nadal rzuca.
5. **Granica Faza 3 / Faza 4.** Faza 3 dodaje `wybrany_kandydat` (FK Autor, wybór
   przy `wielu`) i `korekta_uzytkownika` (JSON). Pole `utworz_nowego` (dla `brak`)
   i tworzenie nowego autora to **Faza 4** — NIE implementować. W Fazie 3 wiersz
   `brak` przy integracji jest POMIJANY; `wielu` z ustawionym `wybrany_kandydat` →
   materializuje `row.autor` i integruje; `wielu` bez wyboru → pomijany
   (rozpoznawalny przez `confidence in {brak,wielu}` i `autor is None`).
6. **Edycja inline (HTMX).** POST na pojedynczy wiersz z poprawionymi
   `imiona`/`nazwisko`/`tytul` → zapis do `korekta_uzytkownika` → SYNCHRONICZNIE
   ponów match (znajdz_kandydatow_autora + oblicz_status_pewnosci) → nadpisz
   `confidence`/kandydatów/`autor` → zwróć wyrenderowany partial wiersza.
   Owner-scoped, `GroupRequiredMixin`. Wybór kandydata = osobny POST ustawiający
   `wybrany_kandydat` → materializuje `row.autor` i przelicza `zmiany_potrzebne`.

## Assumptions / otwarte ryzyka (wpisane do planu)

- **A1.** `import_common.core.autor` eksportuje `PEWNOSC_IEXACT=1.0`,
  `PEWNOSC_MIN_AUTOMATYCZNA=0.85`, `KandydatAutora`, `znajdz_kandydatow_autora`.
  Stałe `PEWNOSC_*` NIE są re-eksportowane z `import_common.core.__init__` —
  importujemy je z `import_common.core.autor` bezpośrednio (`KandydatAutora`/
  `znajdz_kandydatow_autora` są re-eksportowane, ale dla spójności bierzemy je z
  `.autor` również).
- **A2.** `osoba_sklejona` NIE ma jeszcze w `mapping.POLA_DOCELOWE` (Faza 2 świadomie
  ją wykluczyła, a test `test_pola_docelowe_zawieraja_kluczowe_pola` asertuje jej
  brak). Faza 3 DODAJE ją (Task 5) i **aktualizuje** ten test.
- **A3.** `AutorForm` wymaga `nazwisko` ORAZ `imię`. Gdy `osoba_sklejona` rozbije
  się na sam nazwisko (jeden token) albo pustą osobę → `imię` puste → `AutorForm`
  padnie `XLSParseError` (jak dziś). Zdegenerowane pojedyncze komórki NIE stają się
  statusem `brak` — to świadome ograniczenie Fazy 3 (Faza 4 może złagodzić przez
  osobną walidację). Status `brak` obejmuje wiersze, gdzie parser dał imię+nazwisko,
  ale `znajdz_kandydatow_autora` zwróciło pustą listę.
- **A4.** Status `zgadywanie` (PL↔EN, pewnosc 0.85, pojedynczy kandydat) wymaga
  rozszerzenia `unaccent` (jest w testcontainers baseline). Ścieżkę `zgadywanie`
  wyczerpująco pokrywają czyste testy Taska 1 (syntetyczne `KandydatAutora`); test
  integracyjny pipeline (Task 7) skupia się na odpornych `twardy`/`brak`/`wielu`.
- **A5.** HTMX ładowany z `https://unpkg.com/htmx.org@2.0.4` (jak
  `importer_publikacji/index.html`) — nie ma go w publicznym `base.html`, więc
  szablon podglądu dokłada `<script src=...>` w bloku, w którym renderuje kontrolki.
- **A6.** Realne pliki kadrowe (§13 spec) jeszcze nie dotarły; statyczne leksykony
  tytułów/imion (Task 4) i fixtures są oparte na wzorcu BPP + domenie — możliwe luki
  w nietypowych zapisach tytułów. Rozszerzalne bez zmian architektury.
- **A7.** `make baseline-update` robimy **przy merge**, nie na tym branchu.

## Kontekst i wzorce (przeczytaj przed implementacją)

- **Faza 2 plan (styl):** `docs/superpowers/plans/2026-07-09-import-pracownikow-faza-2-mapowanie.md`.
- **Spec §7 (parser), §8 (status pewności), §12 (struktura plików), §13/§14:**
  `docs/superpowers/specs/2026-07-09-import-pracownikow-elastyczny-design.md`.
- **Kandydaci/progi:** `src/import_common/core/autor.py` —
  `znajdz_kandydatow_autora(imiona, nazwisko, *, max_wyniki=10) -> list[KandydatAutora]`
  (puste imię/nazwisko → `[]`, lista DESC po `pewnosc`); `KandydatAutora(autor,
  pewnosc, powod, publikacji)` (frozen dataclass); `PEWNOSC_IEXACT`,
  `PEWNOSC_MIN_AUTOMATYCZNA`; `matchuj_autora(imiona, nazwisko, jednostka=None,
  bpp_id=None, pbn_uid_id=None, system_kadrowy_id=None, pbn_id=None, orcid=None,
  tytul_str=None) -> Autor|None`.
- **Wzorzec modelu kandydata:** `src/importer_publikacji/models.py:384`
  (`ImportedAuthor_Candidate`).
- **Pipeline analizy:** `src/import_pracownikow/pipeline/analyze.py` —
  `_przetworz_wiersz(parent, elem)` (dziś rzuca `XLSMatchError` gdy autor None,
  linie ~126–133), `analizuj(parent, p)`.
- **Pipeline integracji:** `src/import_pracownikow/pipeline/integrate.py` —
  `integruj(parent, p)`, iteruje `zmiany_potrzebne_set`.
- **Model:** `src/import_pracownikow/models.py` — `ImportPracownikowRow`
  (`autor` nullable FK, `dane_znormalizowane` JSON, `diff_do_utworzenia`,
  `zmiany_potrzebne`, `check_if_integration_needed()`); `get_details_set()`.
- **Widoki/URL:** `src/import_pracownikow/views.py`
  (`ImportPracownikowResultsView`, `GROUP_REQUIRED="wprowadzanie danych"`),
  `src/import_pracownikow/urls.py`.
- **Szablon podglądu:**
  `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`.
- **HTMX partial (wzorzec):**
  `src/importer_publikacji/templates/importer_publikacji/partials/` +
  `index.html:52-55` (include skryptu unpkg).

---

## File Structure

**Tworzone:**
- `src/import_pracownikow/pewnosc.py` — `STATUS_*`, `STATUS_CHOICES`,
  `STATUS_DISPLAY`, `oblicz_status_pewnosci`, `wybierz_autora_z_kandydatow`,
  `odtworz_autor_jednostka`.
- `src/import_pracownikow/parsers/osoba.py` — `WynikRozbicia`, `rozbij_osobe`,
  `CONF_HIGH/MEDIUM/LOW`.
- `src/import_pracownikow/parsers/leksykony.py` — `ParserKontekst`,
  `zbuduj_parser_kontekst` (+ `zbuduj_tytuly`/`zbuduj_imiona_znane`/
  `zbuduj_probuj_match`).
- `src/import_pracownikow/migrations/0013_confidence_kandydaci.py` (generowana).
- `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`.
- `src/import_pracownikow/tests/test_pewnosc.py`
- `src/import_pracownikow/tests/test_parsers/test_osoba.py`
- `src/import_pracownikow/tests/test_parsers/test_leksykony.py`
- `src/import_pracownikow/tests/test_models/test_kandydaci_model.py`
- `src/import_pracownikow/tests/test_pipeline/test_analyze_osoba.py`
- `src/import_pracownikow/tests/test_pipeline/test_analyze_status.py`
- `src/import_pracownikow/tests/test_pipeline/test_integrate_status.py`
- `src/import_pracownikow/tests/test_views_wiersz.py`
- `src/import_pracownikow/tests/test_views_preview_render.py`
- `src/import_pracownikow/tests/test_pipeline/test_faza3_e2e.py`
- `src/bpp/newsfragments/import-pracownikow-parser-pewnosc.feature.rst`

**Modyfikowane:**
- `src/import_pracownikow/models.py` — pola `confidence`/`korekta_uzytkownika`/
  `wybrany_kandydat`, model `ImportPracownikowRowKandydat`, property
  `confidence_badge`.
- `src/import_pracownikow/mapping.py` — `osoba_sklejona` w `POLA_DOCELOWE`,
  synonimy, relaksacja `waliduj_mapowanie`.
- `src/import_pracownikow/tests/test_mapping.py` — aktualizacja asercji
  `osoba_sklejona`.
- `src/import_pracownikow/pipeline/analyze.py` — wstrzyknięcie parsera + status.
- `src/import_pracownikow/pipeline/integrate.py` — licznik pominiętych brak/wielu.
- `src/import_pracownikow/views.py` — `WybierzKandydataView`, `EdytujWierszView`,
  reorder `ImportPracownikowResultsView.get_queryset`.
- `src/import_pracownikow/urls.py` — trasy `wybierz-kandydata`, `edytuj-wiersz`.
- `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`.
- `src/import_pracownikow/tests/test_views_liveops.py` — regresja audytu „Lista
  modyfikacji" po przepisaniu szablonu (Task 11; ewentualna aktualizacja asercji).

**Poza zakresem (Faza 4/5 — nie flagować jako braki):** `utworz_nowego` +
tworzenie nowego autora, `ImportPracownikowOdpiecie`, przepięcie prac.
**Preselekcja kandydata jednostką/tytułem w dropdownie `wielu`** (spec §8) —
ŚWIADOMIE odłożona (decyzja F7 b): dropdown sortuje kandydatów wyłącznie po
`-pewnosc`, user wybiera ręcznie. Oznaczanie „preselektowanego" kandydata (tego,
którego `autor` ma `Autor_Jednostka` z `row.jednostka`) wymaga dodatkowego
zapytania per kandydat / adnotacji queryset — dokładamy w późniejszej iteracji,
gdy dojdą realne pliki kadrowe (A6) i zobaczymy realny rozkład `wielu`.

---

### Task 1: `pewnosc.py` — status pewności (czysta funkcja + stałe)

Rdzeń §8: czysta funkcja liczy status z listy kandydatów. Stałe `STATUS_*` żyją tu
(nie na modelu), żeby model, pipeline i widoki miały jedno źródło prawdy bez
importu ORM w warstwie logiki.

**Files:**
- Create: `src/import_pracownikow/pewnosc.py`
- Test: `src/import_pracownikow/tests/test_pewnosc.py`

**Interfaces:**
- Consumes: `import_common.core.autor.PEWNOSC_IEXACT` (1.0),
  `PEWNOSC_MIN_AUTOMATYCZNA` (0.85); `KandydatAutora` (pole `.pewnosc: float`).
- Produces:
  - `STATUS_TWARDY="twardy"`, `STATUS_ZGADYWANIE="zgadywanie"`,
    `STATUS_WIELU="wielu"`, `STATUS_BRAK="brak"`.
  - `STATUS_CHOICES: list[tuple[str, str]]`.
  - `STATUS_DISPLAY: dict[str, tuple[str, str, str]]` — `status → (klasa_label,
    ikona_foundation, etykieta)`.
  - `oblicz_status_pewnosci(kandydaci: list[KandydatAutora], *, match_po_id: bool)
    -> str`.
  - `wybierz_autora_z_kandydatow(kandydaci: list[KandydatAutora], status: str)
    -> Autor | None` — wspólna reguła materializacji autora (`kandydaci[0].autor`
    dla `twardy`/`zgadywanie`, inaczej `None`); używana przez analizę (T7) i
    re-match inline (T10), żeby nie duplikować reguły.
  - `odtworz_autor_jednostka(row, autor) -> None` — po zmianie autora wiersza
    (wybór kandydata T9 / korekta inline T10) ZAWSZE zdejmuje ewentualny
    nieaktualny `diff_do_utworzenia["autor_jednostka"]` (od poprzedniego autora),
    podpina istniejące `Autor_Jednostka` (lub odkłada create w diffie) i przelicza
    `zmiany_potrzebne`. JEDYNA funkcja w tym module sięgająca ORM — przez LAZY
    import wewnątrz ciała (`from bpp.models import Autor_Jednostka`), więc ładowanie
    modułu pozostaje ORM-free (model dalej może importować `STATUS_*`). NIE zapisuje
    wiersza (caller składa `save`/`update_fields`). Współdzielona przez T9 i T10,
    żeby reguła AJ nie była powielona (T7 zostaje inline — inny kształt: operuje na
    lokalnym `diff` przed konstrukcją wiersza).

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_pewnosc.py`:

```python
from dataclasses import dataclass

from import_common.core.autor import (
    PEWNOSC_IEXACT,
    PEWNOSC_INICJAL,
    PEWNOSC_MIN_AUTOMATYCZNA,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
    STATUS_ZGADYWANIE,
    oblicz_status_pewnosci,
    wybierz_autora_z_kandydatow,
)


@dataclass
class _Kand:
    pewnosc: float


@dataclass
class _KandZAutorem:
    autor: object


def _kandydaci(*pewnosci):
    return [_Kand(p) for p in pewnosci]


def test_brak_gdy_pusta_lista():
    assert oblicz_status_pewnosci([], match_po_id=False) == STATUS_BRAK


def test_twardy_po_id_niezaleznie_od_kandydatow():
    assert oblicz_status_pewnosci([], match_po_id=True) == STATUS_TWARDY
    assert (
        oblicz_status_pewnosci(_kandydaci(0.5), match_po_id=True) == STATUS_TWARDY
    )


def test_twardy_pojedynczy_iexact():
    kand = _kandydaci(PEWNOSC_IEXACT)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_TWARDY


def test_zgadywanie_pojedynczy_powyzej_progu_ponizej_jeden():
    kand = _kandydaci(PEWNOSC_MIN_AUTOMATYCZNA)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_ZGADYWANIE


def test_wielu_remis_na_najwyzszym_tierze():
    kand = _kandydaci(PEWNOSC_IEXACT, PEWNOSC_IEXACT)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_WIELU


def test_wielu_gdy_najlepszy_ponizej_progu():
    kand = _kandydaci(PEWNOSC_INICJAL)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_WIELU


def test_pojedynczy_najwyzszy_nad_reszta_to_nie_remis():
    # top_tier ma DOKŁADNIE 1 (0.85 = PEWNOSC_MIN_AUTOMATYCZNA) mimo drugiego,
    # słabszego kandydata (0.5 = PEWNOSC_INICJAL)
    kand = _kandydaci(PEWNOSC_MIN_AUTOMATYCZNA, PEWNOSC_INICJAL)
    assert oblicz_status_pewnosci(kand, match_po_id=False) == STATUS_ZGADYWANIE


def test_wybierz_autora_z_kandydatow_dla_twardy_i_zgadywanie():
    kand = [_KandZAutorem("A"), _KandZAutorem("B")]
    assert wybierz_autora_z_kandydatow(kand, STATUS_TWARDY) == "A"
    assert wybierz_autora_z_kandydatow(kand, STATUS_ZGADYWANIE) == "A"


def test_wybierz_autora_z_kandydatow_none_dla_wielu_brak_i_pustych():
    kand = [_KandZAutorem("A"), _KandZAutorem("B")]
    assert wybierz_autora_z_kandydatow(kand, STATUS_WIELU) is None
    assert wybierz_autora_z_kandydatow(kand, STATUS_BRAK) is None
    assert wybierz_autora_z_kandydatow([], STATUS_TWARDY) is None
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pewnosc.py -v`
Expected: FAIL (`ModuleNotFoundError: ...pewnosc`).

- [ ] **Step 3: Implementuj `pewnosc.py`**

Utwórz `src/import_pracownikow/pewnosc.py`:

```python
"""Status pewności dopasowania autora (§8 spec).

Czysta funkcja ``oblicz_status_pewnosci`` liczy status WPROST z listy kandydatów
zwróconej przez ``import_common.core.autor.znajdz_kandydatow_autora`` (posortowanej
malejąco po ``pewnosc``) — NIE z ``matchuj_autora`` (poza priorytetową ścieżką po
ID, sygnalizowaną ``match_po_id``). Stałe ``STATUS_*`` mieszkają tutaj, a nie na
modelu, żeby model, pipeline i widoki dzieliły jedno źródło prawdy bez importu ORM
w warstwie logiki.
"""

from import_common.core.autor import PEWNOSC_IEXACT, PEWNOSC_MIN_AUTOMATYCZNA

STATUS_TWARDY = "twardy"
STATUS_ZGADYWANIE = "zgadywanie"
STATUS_WIELU = "wielu"
STATUS_BRAK = "brak"

STATUS_CHOICES = [
    (STATUS_TWARDY, "twardy match"),
    (STATUS_ZGADYWANIE, "zgadywanie"),
    (STATUS_WIELU, "wielu kandydatów"),
    (STATUS_BRAK, "brak dopasowania"),
]

# status → (klasa Foundation label, ikona Foundation-Icons, etykieta). Foundation
# labels (success/warning/primary/secondary) są w built-in CSS — bez SCSS/grunt.
STATUS_DISPLAY = {
    STATUS_TWARDY: ("success", "fi-check", "twardy match"),
    STATUS_ZGADYWANIE: ("warning", "fi-flag", "zgadywanie"),
    STATUS_WIELU: ("primary", "fi-page-multiple", "wielu kandydatów"),
    STATUS_BRAK: ("secondary", "fi-minus-circle", "brak dopasowania"),
}


def oblicz_status_pewnosci(kandydaci, *, match_po_id):
    """Zwraca jeden ze ``STATUS_*`` dla listy ``KandydatAutora`` (DESC po
    ``pewnosc``). Reguła „czystego zwycięzcy": ``twardy``/``zgadywanie`` wymaga
    DOKŁADNIE jednego kandydata na najwyższym tierze; remis → ``wielu``."""
    if match_po_id:
        return STATUS_TWARDY
    if not kandydaci:
        return STATUS_BRAK

    najwyzsza = kandydaci[0].pewnosc
    top_tier = [k for k in kandydaci if k.pewnosc == najwyzsza]

    if len(top_tier) >= 2:
        return STATUS_WIELU
    if najwyzsza < PEWNOSC_MIN_AUTOMATYCZNA:
        return STATUS_WIELU
    if najwyzsza == PEWNOSC_IEXACT:
        return STATUS_TWARDY
    return STATUS_ZGADYWANIE


def wybierz_autora_z_kandydatow(kandydaci, status):
    """Autor materializowany z listy kandydatów dla statusu twardy/zgadywanie
    (pierwszy = najpewniejszy, lista DESC po ``pewnosc``). Dla ``wielu``/``brak``
    → ``None`` (decyzję podejmuje user). Wspólne źródło reguły dla analizy (T7)
    i re-matchu inline (T10), żeby ``kandydaci[0].autor if status in {...}`` nie
    było powielone w dwóch miejscach."""
    if status in (STATUS_TWARDY, STATUS_ZGADYWANIE) and kandydaci:
        return kandydaci[0].autor
    return None


def odtworz_autor_jednostka(row, autor):
    """Po zmianie autora wiersza (wybór kandydata T9 / korekta inline T10)
    ustawia powiązanie ``Autor_Jednostka`` i porządkuje ``diff_do_utworzenia``:

    - ZAWSZE zdejmuje ewentualny nieaktualny wpis ``autor_jednostka`` (odłożony
      dla POPRZEDNIEGO autora) — inaczej integracja (``_materializuj_diff``)
      utworzyłaby AJ dla już-nie-autora wiersza i nadpisała ``row.autor_jednostka``
      (korupcja danych: dane zatrudnienia nowego autora lądują u starego),
    - gdy AJ ``(autor, jednostka)`` istnieje: podpina je i przelicza
      ``zmiany_potrzebne`` z realnej różnicy (``check_if_integration_needed`` czyta
      ``self.autor_jednostka``, więc nie może zostać ``None``),
    - gdy AJ brak: odkłada create w ``diff_do_utworzenia`` i ustawia
      ``zmiany_potrzebne=True`` (integracja zmaterializuje AJ przez ``get_or_create``).

    NIE zapisuje wiersza — caller składa ``save``/``update_fields``. Caller MUSI
    ustawić ``row.autor = autor`` PRZED wywołaniem (``check_if_integration_needed``
    czyta ``self.autor``). Jedyna funkcja w module sięgająca ORM: import
    ``Autor_Jednostka`` jest LAZY (w ciele), więc ładowanie modułu pozostaje
    ORM-free i ``models.py`` dalej może importować ``STATUS_*``.
    """
    from bpp.models import Autor_Jednostka

    row.diff_do_utworzenia.pop("autor_jednostka", None)
    aj = Autor_Jednostka.objects.filter(
        autor=autor, jednostka=row.jednostka
    ).first()
    row.autor_jednostka = aj
    if aj is None:
        row.diff_do_utworzenia["autor_jednostka"] = {
            "autor": autor.pk,
            "jednostka": row.jednostka_id,
        }
        row.zmiany_potrzebne = True
    else:
        row.zmiany_potrzebne = bool(row.diff_do_utworzenia) or (
            row.check_if_integration_needed()
        )
```

Uwaga: `odtworz_autor_jednostka` wymaga bazy — jej testy (jednostkowy + regresja
korupcji AJ) żyją w `test_views_wiersz.py` (T9), gdzie są już fixtures DB i widok,
który ją wywołuje; `test_pewnosc.py` pozostaje czyste (atrapy, bez ORM).

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pewnosc.py -v`
Expected: PASS (9).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/pewnosc.py \
  src/import_pracownikow/tests/test_pewnosc.py
git commit -m "feat(import_pracownikow): oblicz_status_pewnosci + stałe STATUS_* (Faza 3 T1)"
```

---

### Task 2: Migracja + pola confidence/korekta/wybrany_kandydat + model kandydata

**Files:**
- Modify: `src/import_pracownikow/models.py` (pola na `ImportPracownikowRow`,
  property `confidence_badge`, model `ImportPracownikowRowKandydat`)
- Create: `src/import_pracownikow/migrations/0013_confidence_kandydaci.py` (gen.)
- Test: `src/import_pracownikow/tests/test_models/test_kandydaci_model.py`

**Interfaces:**
- Consumes: `pewnosc.STATUS_CHOICES`, `pewnosc.STATUS_DISPLAY`,
  `pewnosc.STATUS_TWARDY` (Task 1).
- Produces:
  - `ImportPracownikowRow.confidence` (CharField, choices=STATUS_CHOICES,
    null/blank).
  - `ImportPracownikowRow.korekta_uzytkownika` (JSONField, default=dict, blank).
  - `ImportPracownikowRow.wybrany_kandydat` (FK bpp.Autor, null/blank,
    on_delete=SET_NULL, related_name="+").
  - `ImportPracownikowRow.confidence_badge -> tuple[str, str, str]`.
  - `ImportPracownikowRowKandydat(row FK related_name="kandydaci", autor FK,
    pewnosc Float, powod Char(32), publikacji_count PositiveInt default 0)`.
  - `ImportPracownikowRowKandydat.zapisz_dla(row, kandydaci: list[KandydatAutora])
    -> None` (classmethod) — kasuje dotychczasowych kandydatów wiersza i tworzy
    nowych (`bulk_create`) z mapowania `k.autor/k.pewnosc/k.powod/k.publikacji →
    autor/pewnosc/powod/publikacji_count`. Jedno źródło zapisu kandydatów dla
    analizy (T7) i re-matchu inline (T10).

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_models/test_kandydaci_model.py`:

```python
import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_TWARDY, STATUS_WIELU


@pytest.mark.django_db
def test_row_ma_nowe_pola_z_bezpiecznymi_defaultami():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(parent=imp, zmiany_potrzebne=False)
    row.save()
    row.refresh_from_db()
    assert row.confidence is None
    assert row.korekta_uzytkownika == {}
    assert row.wybrany_kandydat is None


@pytest.mark.django_db
def test_confidence_badge_mapuje_status_na_klase_i_ikone():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_TWARDY
    )
    klasa, ikona, etykieta = row.confidence_badge
    assert klasa == "success"
    assert ikona == "fi-check"
    assert "twardy" in etykieta


@pytest.mark.django_db
def test_confidence_badge_dla_none_ma_bezpieczny_default():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(parent=imp, zmiany_potrzebne=False, confidence=None)
    klasa, ikona, etykieta = row.confidence_badge
    assert klasa == "secondary"


@pytest.mark.django_db
def test_kandydat_zapis_i_odczyt_oraz_ordering():
    from bpp.models import Autor

    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_WIELU
    )
    row.save()
    a1 = baker.make(Autor, nazwisko="A", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="B", imiona="Jan")
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=0.85, powod="polish_english", publikacji_count=3
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a2, pewnosc=1.0, powod="iexact", publikacji_count=1
    )
    kandydaci = list(row.kandydaci.all())
    assert len(kandydaci) == 2
    # ordering ["-pewnosc"] — najpewniejszy pierwszy
    assert kandydaci[0].autor_id == a2.pk
    assert kandydaci[0].pewnosc == 1.0


@pytest.mark.django_db
def test_zapisz_dla_nadpisuje_kandydatow_wiersza():
    from dataclasses import dataclass

    from bpp.models import Autor

    @dataclass
    class _K:
        autor: object
        pewnosc: float
        powod: str
        publikacji: int

    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_WIELU
    )
    row.save()
    a1 = baker.make(Autor, nazwisko="A", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="B", imiona="Jan")

    ImportPracownikowRowKandydat.zapisz_dla(row, [_K(a1, 1.0, "iexact", 2)])
    assert row.kandydaci.count() == 1

    # ponowne wywołanie KASUJE poprzednich i wstawia nowych (mapowanie k.* → pola)
    ImportPracownikowRowKandydat.zapisz_dla(
        row, [_K(a2, 0.85, "polish_english", 0)]
    )
    kandydaci = list(row.kandydaci.all())
    assert len(kandydaci) == 1
    assert kandydaci[0].autor_id == a2.pk
    assert kandydaci[0].powod == "polish_english"
    assert kandydaci[0].publikacji_count == 0
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_kandydaci_model.py -v`
Expected: FAIL (`ImportError: cannot import name 'ImportPracownikowRowKandydat'`).

- [ ] **Step 3: Dodaj pola + property + model do `models.py`**

W `src/import_pracownikow/models.py`, u góry (po istniejących importach), dodaj:

```python
from import_pracownikow.pewnosc import STATUS_CHOICES, STATUS_DISPLAY
```

W klasie `ImportPracownikowRow`, PO polu `pominiety_bo_nieaktualny = ...`, dodaj
pola:

```python
    confidence = models.CharField(
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )
    korekta_uzytkownika = models.JSONField(default=dict, blank=True)
    wybrany_kandydat = models.ForeignKey(
        "bpp.Autor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
```

W tej samej klasie dodaj property (obok `dane_bardziej_znormalizowane`):

```python
    @property
    def confidence_badge(self):
        """(klasa Foundation label, ikona Foundation-Icons, etykieta) dla
        ``confidence`` — do szablonu podglądu. ``None`` (stare wiersze) →
        bezpieczny neutralny badge."""
        return STATUS_DISPLAY.get(
            self.confidence, ("secondary", "fi-minus", self.confidence or "—")
        )
```

Na końcu pliku (po `ProfilMapowania`) dodaj model kandydata (wzorzec
`importer_publikacji.models.ImportedAuthor_Candidate:384`):

```python
class ImportPracownikowRowKandydat(models.Model):
    """Kandydat na dopasowanie autora dla wiersza o statusie ``wielu``.

    Materializuje listę z ``znajdz_kandydatow_autora`` (pewność, powód strategii,
    liczba publikacji), żeby dropdown w podglądzie mógł pokazać userowi pełny
    kontekst. Wzorzec: ``importer_publikacji.ImportedAuthor_Candidate``.
    """

    row = models.ForeignKey(
        ImportPracownikowRow,
        on_delete=models.CASCADE,
        related_name="kandydaci",
        verbose_name="wiersz importu",
    )
    autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.CASCADE,
        verbose_name="autor BPP",
    )
    pewnosc = models.FloatField("pewność")
    powod = models.CharField("powód dopasowania", max_length=32)
    publikacji_count = models.PositiveIntegerField("liczba publikacji", default=0)

    class Meta:
        verbose_name = "kandydat na autora (import pracowników)"
        verbose_name_plural = "kandydaci na autora (import pracowników)"
        ordering = ["-pewnosc"]

    def __str__(self):
        return f"{self.autor} ({self.pewnosc})"

    @classmethod
    def zapisz_dla(cls, row, kandydaci):
        """Nadpisuje kandydatów wiersza listą ``KandydatAutora`` (z
        ``znajdz_kandydatow_autora``): kasuje poprzednich i tworzy nowych
        (``bulk_create``). Jedno źródło mapowania ``k.* → pola modelu`` dla
        analizy (T7) oraz re-matchu inline (T10). Przekaż ``[]``, by tylko
        wyczyścić kandydatów (np. wiersz po korekcie zszedł z ``wielu``)."""
        row.kandydaci.all().delete()
        cls.objects.bulk_create(
            [
                cls(
                    row=row,
                    autor=k.autor,
                    pewnosc=k.pewnosc,
                    powod=k.powod,
                    publikacji_count=k.publikacji,
                )
                for k in kandydaci
            ]
        )
```

- [ ] **Step 4: Wygeneruj migrację**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --name confidence_kandydaci`
Expected: utworzony `0013_confidence_kandydaci.py` (AddField ×3 + CreateModel
`ImportPracownikowRowKandydat`). **NIE** edytuj ręcznie.

- [ ] **Step 5: Sprawdź brak driftu**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: „No changes detected".

- [ ] **Step 6: Uruchom testy — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_kandydaci_model.py -v`
Expected: PASS (5).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/models.py \
  src/import_pracownikow/migrations/0013_confidence_kandydaci.py \
  src/import_pracownikow/tests/test_models/test_kandydaci_model.py
git commit -m "feat(import_pracownikow): pola confidence/korekta/wybrany_kandydat + model kandydata (Faza 3 T2)"
```

---

### Task 3: Parser rdzeń `parsers/osoba.py` (czysty, testy tabelaryczne)

Rdzeń §7: czysta tokenizacja + reguły składania, bez ORM. Sygnał bazodanowy i
słowniki wstrzykiwane jako argumenty.

**Files:**
- Create: `src/import_pracownikow/parsers/osoba.py`
- Test: `src/import_pracownikow/tests/test_parsers/test_osoba.py`

**Interfaces:**
- Produces:
  - `CONF_HIGH="high"`, `CONF_MEDIUM="medium"`, `CONF_LOW="low"`.
  - `WynikRozbicia(tytul: str|None, imiona: str, nazwisko: str, confidence: str,
    alternatywy: list[dict])` (frozen dataclass).
  - `rozbij_osobe(tekst: str, *, tytuly: set[str], imiona_znane: set[str],
    probuj_match: Callable[[str, str], bool]) -> WynikRozbicia`.

- [ ] **Step 1: Napisz failing testy tabelaryczne**

Utwórz `src/import_pracownikow/tests/test_parsers/test_osoba.py`:

```python
import pytest

from import_pracownikow.parsers.osoba import (
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    rozbij_osobe,
)


def _tylko(*pary):
    dozwolone = {(i.strip(), n.strip()) for i, n in pary}
    return lambda im, nz: (im.strip(), nz.strip()) in dozwolone


def _bez(im, nz):
    return False


def _wszystko(im, nz):
    return True


PRZYPADKI = [
    # (tekst, tytuly, imiona_znane, probuj_match,
    #  tytul, imiona, nazwisko, confidence)
    (
        "dr Jan Kowalski", {"dr"}, set(), _tylko(("Jan", "Kowalski")),
        "dr", "Jan", "Kowalski", CONF_HIGH,
    ),
    (
        "Jan Kowalski prof.", {"prof."}, set(), _tylko(("Jan", "Kowalski")),
        "prof.", "Jan", "Kowalski", CONF_HIGH,
    ),
    (
        "Kowalska-Nowak, Anna Maria", set(), set(), _bez,
        None, "Anna Maria", "Kowalska-Nowak", CONF_HIGH,
    ),
    (
        "KOWALSKI Jan", set(), set(), _bez,
        None, "Jan", "KOWALSKI", CONF_HIGH,
    ),
    (
        "Anna Nowak", set(), set(), _tylko(("Anna", "Nowak")),
        None, "Anna", "Nowak", CONF_HIGH,
    ),
    (
        "Nowak Anna", set(), {"anna"}, _bez,
        None, "Anna", "Nowak", CONF_MEDIUM,
    ),
    (
        "Anna Kowalska-Nowak", set(), set(), _bez,
        None, "Anna", "Kowalska-Nowak", CONF_MEDIUM,
    ),
    (
        "dr hab. Anna Maria Nowak", {"dr hab."}, {"anna", "maria"}, _bez,
        "dr hab.", "Anna Maria", "Nowak", CONF_MEDIUM,
    ),
    (
        "prof. dr hab. n. med. Jan Kowalski",
        {"prof. dr hab. n. med.", "dr", "prof."}, set(),
        _tylko(("Jan", "Kowalski")),
        "prof. dr hab. n. med.", "Jan", "Kowalski", CONF_HIGH,
    ),
    (
        "Xyz Qwe", set(), set(), _bez,
        None, "Xyz", "Qwe", CONF_LOW,
    ),
    (
        "Jan Piotr", set(), set(), _wszystko,
        None, "Jan", "Piotr", CONF_LOW,
    ),
    (
        # A3: zdegenerowana komórka (jeden token) → puste imiona, całość jako
        # nazwisko, CONF_LOW. Pipeline i tak odrzuci to AutorForm-em (test w T6).
        "Kowalski", set(), set(), _bez,
        None, "", "Kowalski", CONF_LOW,
    ),
]


@pytest.mark.parametrize(
    "tekst,tytuly,imiona_znane,probuj,tytul,imiona,nazwisko,confidence",
    PRZYPADKI,
)
def test_rozbij_osobe_tabelarycznie(
    tekst, tytuly, imiona_znane, probuj, tytul, imiona, nazwisko, confidence
):
    wynik = rozbij_osobe(
        tekst, tytuly=tytuly, imiona_znane=imiona_znane, probuj_match=probuj
    )
    assert wynik.tytul == tytul
    assert wynik.imiona == imiona
    assert wynik.nazwisko == nazwisko
    assert wynik.confidence == confidence


def test_low_confidence_ma_alternatywe_odwroconej_kolejnosci():
    wynik = rozbij_osobe("Xyz Qwe", tytuly=set(), imiona_znane=set(), probuj_match=_bez)
    assert wynik.confidence == CONF_LOW
    assert wynik.alternatywy
    alt = wynik.alternatywy[0]
    assert alt["imiona"] == "Qwe"
    assert alt["nazwisko"] == "Xyz"


def test_wysoka_pewnosc_bez_alternatyw():
    wynik = rozbij_osobe(
        "Anna Nowak", tytuly=set(), imiona_znane=set(),
        probuj_match=_tylko(("Anna", "Nowak")),
    )
    assert wynik.confidence == CONF_HIGH
    assert wynik.alternatywy == []
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_osoba.py -v`
Expected: FAIL (`ModuleNotFoundError: ...parsers.osoba`).

- [ ] **Step 3: Implementuj `parsers/osoba.py`**

Utwórz `src/import_pracownikow/parsers/osoba.py`:

```python
"""Rozbicie sklejonej komórki „tytuł+imię+nazwisko" (§7 spec).

Czysty rdzeń — bez ORM. Słowniki tytułów/imion oraz callable ``probuj_match``
(sygnał bazodanowy) są wstrzykiwane; adapter (``parsers.leksykony``) dostarcza
realne wartości z bazy. Testy tabelaryczne odpalają rdzeń z atrapami.
"""

from collections.abc import Callable
from dataclasses import dataclass

CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_LOW = "low"

# Maksymalna długość frazy tytułu (w tokenach), np. „prof. dr hab. n. med." = 5.
_MAX_TYTUL_TOKENOW = 6


@dataclass(frozen=True)
class WynikRozbicia:
    tytul: str | None
    imiona: str
    nazwisko: str
    confidence: str
    alternatywy: list[dict]


def _jest_wersalikiem(token: str) -> bool:
    """Token ALL-CAPS o długości > 1 z co najmniej jedną literą (nie inicjał)."""
    return len(token) > 1 and token.isupper() and any(c.isalpha() for c in token)


def _dopasuj_od_przodu(tokeny_lower: list[str], tytuly: set[str]) -> int:
    for dlugosc in range(min(_MAX_TYTUL_TOKENOW, len(tokeny_lower)), 0, -1):
        if " ".join(tokeny_lower[:dlugosc]) in tytuly:
            return dlugosc
    return 0


def _dopasuj_od_tylu(tokeny_lower: list[str], tytuly: set[str]) -> int:
    n = len(tokeny_lower)
    for dlugosc in range(min(_MAX_TYTUL_TOKENOW, n), 0, -1):
        if " ".join(tokeny_lower[n - dlugosc:]) in tytuly:
            return dlugosc
    return 0


def _zdejmij_tytuly(tokeny: list[str], tytuly: set[str]):
    """Iteracyjnie zdejmuje najdłuższe dopasowania tytułów z obu stron. Zwraca
    (start, koniec, fragmenty) — plaster ``tokeny[start:koniec]`` to tokeny nazwy,
    ``fragmenty`` to usunięte frazy tytułu (oryginalna wielkość liter)."""
    start = 0
    koniec = len(tokeny)
    fragmenty: list[str] = []
    while start < koniec:
        lower = [t.lower() for t in tokeny[start:koniec]]
        d = _dopasuj_od_przodu(lower, tytuly)
        if d == 0:
            break
        fragmenty.append(" ".join(tokeny[start:start + d]))
        start += d
    while koniec > start:
        lower = [t.lower() for t in tokeny[start:koniec]]
        d = _dopasuj_od_tylu(lower, tytuly)
        if d == 0:
            break
        fragmenty.append(" ".join(tokeny[koniec - d:koniec]))
        koniec -= d
    return start, koniec, fragmenty


def rozbij_osobe(
    tekst: str,
    *,
    tytuly: set[str],
    imiona_znane: set[str],
    probuj_match: Callable[[str, str], bool],
) -> WynikRozbicia:
    """Rozbija ``tekst`` na tytuł/imiona/nazwisko wg hierarchii sygnałów §7."""
    surowe = (tekst or "").split()
    flagi_przecinka = [t.endswith(",") for t in surowe]
    tokeny = [t.rstrip(",") for t in surowe]

    start, koniec, fragmenty = _zdejmij_tytuly(tokeny, tytuly)
    tytul = " ".join(fragmenty) if fragmenty else None

    nazwy = tokeny[start:koniec]
    flagi = flagi_przecinka[start:koniec]

    if not nazwy:
        return WynikRozbicia(tytul, "", "", CONF_LOW, [])
    if len(nazwy) == 1:
        return WynikRozbicia(tytul, "", nazwy[0], CONF_LOW, [])

    # Sygnał 1: przecinek → nazwisko przed przecinkiem (high).
    k = next((i for i, f in enumerate(flagi) if f), None)
    if k is not None and k + 1 < len(nazwy):
        return WynikRozbicia(
            tytul, " ".join(nazwy[k + 1:]), " ".join(nazwy[: k + 1]), CONF_HIGH, []
        )

    # Sygnał 2: WERSALIKI wśród mixed-case → nazwisko (high).
    wersaliki = [i for i, t in enumerate(nazwy) if _jest_wersalikiem(t)]
    if len(wersaliki) == 1:
        j = wersaliki[0]
        imiona = " ".join(nazwy[:j] + nazwy[j + 1:])
        return WynikRozbicia(tytul, imiona, nazwy[j], CONF_HIGH, [])

    # Sygnał 3: match do bazy obu hipotez — dokładnie jedna True wygrywa (high).
    a = probuj_match(" ".join(nazwy[:-1]), nazwy[-1])
    b = probuj_match(" ".join(nazwy[1:]), nazwy[0])
    if a and not b:
        return WynikRozbicia(tytul, " ".join(nazwy[:-1]), nazwy[-1], CONF_HIGH, [])
    if b and not a:
        return WynikRozbicia(tytul, " ".join(nazwy[1:]), nazwy[0], CONF_HIGH, [])

    # Sygnał 4: leksykon imion — znane imiona → imiona, reszta → nazwisko (medium).
    znane_idx = {i for i, t in enumerate(nazwy) if t.lower() in imiona_znane}
    if znane_idx and len(znane_idx) < len(nazwy):
        imiona = " ".join(nazwy[i] for i in range(len(nazwy)) if i in znane_idx)
        nazwisko = " ".join(nazwy[i] for i in range(len(nazwy)) if i not in znane_idx)
        return WynikRozbicia(tytul, imiona, nazwisko, CONF_MEDIUM, [])

    # Sygnał 5: token z dywizem → prawdopodobnie nazwisko dwuczłonowe (medium).
    dyw_idx = [i for i, t in enumerate(nazwy) if "-" in t or "—" in t]
    if len(dyw_idx) == 1:
        j = dyw_idx[0]
        imiona = " ".join(nazwy[:j] + nazwy[j + 1:])
        return WynikRozbicia(tytul, imiona, nazwy[j], CONF_MEDIUM, [])

    # Fallback bez sygnału: ostatni token = nazwisko (low) + alternatywa odwrócona.
    alternatywy = [
        {
            "imiona": " ".join(nazwy[1:]),
            "nazwisko": nazwy[0],
            "powod": "odwrócona kolejność",
        }
    ]
    return WynikRozbicia(
        tytul, " ".join(nazwy[:-1]), nazwy[-1], CONF_LOW, alternatywy
    )
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_osoba.py -v`
Expected: PASS (14: 12 parametrów + 2 dot. alternatyw).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/parsers/osoba.py \
  src/import_pracownikow/tests/test_parsers/test_osoba.py
git commit -m "feat(import_pracownikow): parser sklejonej osoby rozbij_osobe (Faza 3 T3)"
```

---

### Task 4: Leksykony/adapter `parsers/leksykony.py` (słowniki z bazy)

**Files:**
- Create: `src/import_pracownikow/parsers/leksykony.py`
- Test: `src/import_pracownikow/tests/test_parsers/test_leksykony.py`

**Interfaces:**
- Consumes: `bpp.models.Tytul`/`Autor`,
  `import_common.core.autor.znajdz_kandydatow_autora`.
- Produces:
  - `ParserKontekst(tytuly: set[str], imiona_znane: set[str],
    probuj_match: Callable[[str, str], bool])` (frozen dataclass).
  - `zbuduj_tytuly() -> set[str]`, `zbuduj_imiona_znane() -> set[str]`,
    `zbuduj_probuj_match() -> Callable`, `zbuduj_parser_kontekst() -> ParserKontekst`.

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_parsers/test_leksykony.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Autor, Tytul
from import_pracownikow.parsers.leksykony import (
    zbuduj_imiona_znane,
    zbuduj_parser_kontekst,
    zbuduj_probuj_match,
    zbuduj_tytuly,
)


@pytest.mark.django_db
def test_zbuduj_tytuly_laczy_baze_i_statyke():
    # Tytul.skrot/nazwa są unique, a baseline preloaduje słownik tytułów →
    # get_or_create zamiast baker.make (inaczej IntegrityError na setupie).
    Tytul.objects.get_or_create(
        skrot="prof. dr hab.", defaults={"nazwa": "profesor doktor habilitowany"}
    )
    tytuly = zbuduj_tytuly()
    assert "prof. dr hab." in tytuly  # z bazy (skrot, lower)
    assert "profesor doktor habilitowany" in tytuly  # z bazy (nazwa, lower)
    assert "dr" in tytuly  # ze statyki


@pytest.mark.django_db
def test_zbuduj_imiona_znane_splituje_i_lowercase():
    # Imiona SPOZA statyki (_IMIONA_STATYCZNE), żeby test faktycznie sprawdzał
    # split+lowercase Z BAZY, a nie trafiał w statyczny zbiór (tautologia).
    baker.make(Autor, nazwisko="Kowalski", imiona="Zdzisław Bonifacy")
    imiona = zbuduj_imiona_znane()
    assert "zdzisław" in imiona
    assert "bonifacy" in imiona


@pytest.mark.django_db
def test_zbuduj_probuj_match_true_dla_istniejacego_autora():
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    probuj = zbuduj_probuj_match()
    assert probuj("Jan", "Kowalski") is True
    assert probuj("Nieistniejacy", "Ktostam") is False


@pytest.mark.django_db
def test_zbuduj_parser_kontekst_spina_wszystko():
    baker.make(Autor, nazwisko="Nowak", imiona="Ewa")
    ctx = zbuduj_parser_kontekst()
    assert "dr" in ctx.tytuly
    assert "ewa" in ctx.imiona_znane
    assert ctx.probuj_match("Ewa", "Nowak") is True
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_leksykony.py -v`
Expected: FAIL (`ModuleNotFoundError: ...parsers.leksykony`).

- [ ] **Step 3: Implementuj `parsers/leksykony.py`**

Utwórz `src/import_pracownikow/parsers/leksykony.py`:

```python
"""Adapter: buduje realne słowniki tytułów/imion i callable ``probuj_match`` dla
czystego rdzenia ``parsers.osoba.rozbij_osobe`` (§7 spec).

Rdzeń zostaje czysty (testowalny z atrapami); ten moduł sięga do bazy i do
``znajdz_kandydatow_autora``. ``ParserKontekst`` budujemy RAZ na przebieg analizy
(``analizuj``) i wątkujemy do ``_przetworz_wiersz`` — nie per wiersz.
"""

from collections.abc import Callable
from dataclasses import dataclass

from bpp.models import Autor, Tytul
from import_common.core.autor import znajdz_kandydatow_autora

# Statyczne warianty zapisu tytułów (uzupełniane z realnych plików — §13 spec).
_TYTULY_STATYCZNE = {
    "dr",
    "dr hab.",
    "dr inż.",
    "dr n. med.",
    "dr hab. n. med.",
    "prof.",
    "prof. ucz.",
    "prof. dr hab.",
    "prof. dr hab. n. med.",
    "mgr",
    "mgr inż.",
    "inż.",
    "lek.",
    "lek. med.",
}

# Mała statyczna lista popularnych imion (uzupełniana z bazy w runtime).
_IMIONA_STATYCZNE = {
    "jan", "anna", "piotr", "maria", "andrzej", "katarzyna", "krzysztof",
    "małgorzata", "tomasz", "agnieszka", "paweł", "ewa", "michał", "adam",
    "magdalena", "marcin", "monika", "łukasz", "joanna", "jakub",
}


@dataclass(frozen=True)
class ParserKontekst:
    tytuly: set
    imiona_znane: set
    probuj_match: Callable[[str, str], bool]


def zbuduj_tytuly() -> set:
    """Słownik tytułów: skróty+nazwy z ``bpp.Tytul`` (lower) + statyka."""
    tytuly = set(_TYTULY_STATYCZNE)
    for skrot, nazwa in Tytul.objects.values_list("skrot", "nazwa"):
        if skrot:
            tytuly.add(skrot.strip().lower())
        if nazwa:
            tytuly.add(nazwa.strip().lower())
    return tytuly


def zbuduj_imiona_znane() -> set:
    """Znane imiona: tokeny z ``Autor.imiona`` (splitowane, lower) + statyka."""
    imiona = set(_IMIONA_STATYCZNE)
    for wartosc in Autor.objects.values_list("imiona", flat=True):
        if not wartosc:
            continue
        for token in wartosc.split():
            imiona.add(token.strip().lower())
    return imiona


def zbuduj_probuj_match() -> Callable[[str, str], bool]:
    """Fabryka ``probuj_match(imiona, nazwisko) -> bool`` opartego o
    ``znajdz_kandydatow_autora`` (jest kandydat = hipoteza kolejności trafia)."""

    def probuj(imiona: str, nazwisko: str) -> bool:
        return bool(znajdz_kandydatow_autora(imiona, nazwisko))

    return probuj


def zbuduj_parser_kontekst() -> ParserKontekst:
    """Buduje komplet zależności parsera RAZ (per przebieg analizy)."""
    return ParserKontekst(
        tytuly=zbuduj_tytuly(),
        imiona_znane=zbuduj_imiona_znane(),
        probuj_match=zbuduj_probuj_match(),
    )
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_leksykony.py -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/parsers/leksykony.py \
  src/import_pracownikow/tests/test_parsers/test_leksykony.py
git commit -m "feat(import_pracownikow): adapter leksykonów parsera osoby (Faza 3 T4)"
```

---

### Task 5: `osoba_sklejona` w mapowaniu + relaksacja walidacji identyfikacji

`osoba_sklejona` staje się celem mapowania „1 komórka tytuł+imię+nazwisko"
(§6 spec). Identyfikacja osoby = (nazwisko+imię) LUB osoba_sklejona.

**Files:**
- Modify: `src/import_pracownikow/mapping.py`
- Modify: `src/import_pracownikow/tests/test_mapping.py` (asercja `osoba_sklejona`)

**Interfaces:**
- Produces: `POLA_DOCELOWE` zawiera `("osoba_sklejona", ...)`; `_SYNONIMY` mapuje
  warianty „osoba/nazwisko i imię/imię i nazwisko" → `osoba_sklejona`;
  `waliduj_mapowanie` akceptuje `osoba_sklejona` jako alternatywę dla nazwisko+imię.

- [ ] **Step 1: Zaktualizuj i dodaj testy**

W `src/import_pracownikow/tests/test_mapping.py`, w
`test_pola_docelowe_zawieraja_kluczowe_pola`, ZMIEŃ asercję o `osoba_sklejona`
(była: `not in`) na obecność:

```python
def test_pola_docelowe_zawieraja_kluczowe_pola():
    klucze = {k for k, _ in POLA_DOCELOWE}
    assert {"nazwisko", "imię", "nazwa_jednostki"} <= klucze
    # Faza 3 dodaje kompozyt „osoba sklejona":
    assert "osoba_sklejona" in klucze
```

Dopisz na końcu `test_mapping.py` (importy `zaproponuj_mapowanie`/`POLE_POMIN` już
są na górze pliku z Fazy 2):

```python
def test_synonimy_osoba_sklejona():
    prop = zaproponuj_mapowanie(
        ["nazwisko_i_imię", "imię_i_nazwisko", "osoba", "pracownik"]
    )
    assert prop["nazwisko_i_imię"] == "osoba_sklejona"
    assert prop["imię_i_nazwisko"] == "osoba_sklejona"
    assert prop["osoba"] == "osoba_sklejona"


def test_waliduj_mapowanie_akceptuje_osoba_sklejona_zamiast_nazwisko_imie():
    # osoba_sklejona + jednostka = komplet identyfikacji (bez osobnych nazwisko/imię)
    assert waliduj_mapowanie(
        {"a": "osoba_sklejona", "b": "nazwa_jednostki"}
    ) == []


def test_waliduj_mapowanie_odrzuca_gdy_brak_identyfikacji_i_osoby():
    bledy = waliduj_mapowanie({"b": "nazwa_jednostki"})
    assert any("identyfikac" in e.lower() or "osob" in e.lower() for e in bledy)
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -v`
Expected: FAIL (`osoba_sklejona` nie w `POLA_DOCELOWE`; synonim/walidacja).

- [ ] **Step 3: Zaktualizuj `mapping.py`**

W `src/import_pracownikow/mapping.py` dodaj do `POLA_DOCELOWE` (po `("imię", ...)`):

```python
    ("osoba_sklejona", "Osoba (tytuł+imię+nazwisko w jednej komórce)"),
```

Zaktualizuj komentarz nad `POLA_DOCELOWE` (usuń „tu ich nie ma"):

```python
# Pola docelowe = klucze oczekiwane przez JednostkaForm/AutorForm + kompozyt
# osoba_sklejona (Faza 3 — parser §7 rozbija ją na imię/nazwisko/tytuł).
```

Dodaj synonimy do `_SYNONIMY` (po `"imiona": "imię",`):

```python
    "osoba": "osoba_sklejona",
    "osoba_sklejona": "osoba_sklejona",
    "pracownik": "osoba_sklejona",
    "nazwisko_i_imię": "osoba_sklejona",
    "nazwisko_i_imie": "osoba_sklejona",
    "imię_i_nazwisko": "osoba_sklejona",
    "imie_i_nazwisko": "osoba_sklejona",
    "imię_nazwisko": "osoba_sklejona",
    "imie_nazwisko": "osoba_sklejona",
```

Zamień blok walidacji identyfikacji w `waliduj_mapowanie` (dziś: `brakujace =
_POLA_IDENTYFIKACJI - set(uzyte)` …) na wariant akceptujący `osoba_sklejona`:

```python
    ma_nazwisko_imie = _POLA_IDENTYFIKACJI <= set(uzyte)
    ma_osobe = "osoba_sklejona" in uzyte
    if not (ma_nazwisko_imie or ma_osobe):
        bledy.append(
            "Brak identyfikacji osoby: zmapuj 'nazwisko' + 'imię' albo "
            "'osoba (sklejona)'."
        )
```

(Pozostaw walidację `_POLE_JEDNOSTKA` oraz sprawdzanie duplikatów bez zmian.)

- [ ] **Step 4: Uruchom — zielone (mapping)**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -v`
Expected: PASS (poprzednie + 3 nowe).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/mapping.py \
  src/import_pracownikow/tests/test_mapping.py
git commit -m "feat(import_pracownikow): osoba_sklejona jako cel mapowania + relaksacja walidacji (Faza 3 T5)"
```

---

### Task 6: Pipeline analizy — wstrzyknięcie parsera gdy `osoba_sklejona`

Gdy wiersz ma zmapowaną `osoba_sklejona`, analiza rozbija ją parserem PRZED
walidacją formularzem (zasila imię/nazwisko/tytuł) i zapisuje pewność rozbicia +
alternatywy w `dane_znormalizowane`.

**Files:**
- Modify: `src/import_pracownikow/pipeline/analyze.py`
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze_osoba.py`

**Interfaces:**
- Consumes: `parsers.osoba.rozbij_osobe`, `parsers.leksykony.zbuduj_parser_kontekst`
  / `ParserKontekst` (Task 3/4).
- Produces: `_przetworz_wiersz(parent, elem, parser_ctx=None)` (nowy opcjonalny
  parametr — backward compat: `None` = brak parsera); `analizuj` buduje
  `parser_ctx` RAZ i przekazuje. `dane_znormalizowane["parser_confidence"]` /
  `["parser_alternatywy"]` gdy rozbicie zaszło.

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_analyze_osoba.py`:

```python
from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj


def _wiersz_osoba(osoba, jednostka_nazwa):
    return {
        "osoba_sklejona": osoba,
        "nazwa_jednostki": jednostka_nazwa,
        "wydział": "Wydział Testowy",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }


@pytest.mark.django_db
def test_analiza_rozbija_osobe_sklejona_i_matchuje_autora():
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. Test.")
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    # Tytul.skrot/nazwa unique + baseline preloaduje „dr/doktor" → get_or_create.
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})

    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"

    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [_wiersz_osoba("dr Jan Kowalski", jednostka.nazwa)]
        )
        analizuj(imp, MockProgress(imp))

    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.dane_znormalizowane["nazwisko"] == "Kowalski"
    assert row.dane_znormalizowane["imię"] == "Jan"
    assert row.dane_znormalizowane["parser_confidence"] == "high"
    assert "parser_alternatywy" in row.dane_znormalizowane


@pytest.mark.django_db
def test_osoba_sklejona_jednym_tokenem_rzuca_parse_error():
    # A3: sklejona komórka rozbita na sam nazwisko (jeden token) → imię puste →
    # AutorForm invalid → XLSParseError. To NIE jest status „brak" (założenie A3).
    from import_common.exceptions import XLSParseError

    baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. Test.")
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [_wiersz_osoba("Kowalski", "Katedra Testowa")]
        )
        with pytest.raises(XLSParseError):
            analizuj(imp, MockProgress(imp))
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_osoba.py -v`
Expected: FAIL (osoba_sklejona nie rozbita → `AutorForm` bez nazwiska/imienia →
`XLSParseError`).

- [ ] **Step 3: Wstrzyknij parser do analizy**

W `src/import_pracownikow/pipeline/analyze.py` dodaj importy (po bloku
`import_pracownikow.mapping`):

```python
from import_pracownikow.parsers.leksykony import zbuduj_parser_kontekst
from import_pracownikow.parsers.osoba import rozbij_osobe
```

Zmień sygnaturę `_przetworz_wiersz` i początek (rozbicie osoby PRZED formularzami).
Zamień nagłówek funkcji + pierwsze linie:

```python
def _przetworz_wiersz(parent, elem):
    dane_form = normalizuj_wartosci_wiersza(elem)
    jednostka_form = JednostkaForm(data=dane_form)
```

na:

```python
def _przetworz_wiersz(parent, elem, parser_ctx=None):
    dane_form = normalizuj_wartosci_wiersza(elem)
    rozbicie = None
    if parser_ctx is not None and dane_form.get("osoba_sklejona"):
        rozbicie = rozbij_osobe(
            str(dane_form["osoba_sklejona"]),
            tytuly=parser_ctx.tytuly,
            imiona_znane=parser_ctx.imiona_znane,
            probuj_match=parser_ctx.probuj_match,
        )
        if not dane_form.get("nazwisko"):
            dane_form["nazwisko"] = rozbicie.nazwisko
        if not dane_form.get("imię"):
            dane_form["imię"] = rozbicie.imiona
        if rozbicie.tytul and not dane_form.get("tytuł_stopień"):
            dane_form["tytuł_stopień"] = rozbicie.tytul

    jednostka_form = JednostkaForm(data=dane_form)
```

W tej samej funkcji, tam gdzie budowane jest `dane_znormalizowane=copy(...)`,
zmień tworzenie wiersza tak, by dołożyć metadane parsera. Zamień linię:

```python
        dane_znormalizowane=copy(autor_form.cleaned_data),
```

na:

```python
        dane_znormalizowane=_dane_znormalizowane_z_parserem(
            autor_form.cleaned_data, rozbicie
        ),
```

Dodaj helper (nad `_przetworz_wiersz`):

```python
def _dane_znormalizowane_z_parserem(cleaned_data, rozbicie):
    """Kopia cleaned_data wzbogacona o pewność rozbicia parsera (§7): confidence
    rozbicia (high/medium/low) i alternatywy trzymamy WEWNĄTRZ JSON, nie w
    kolumnie ``confidence`` (ta jest statusem dopasowania AUTORA — §8)."""
    dane = copy(cleaned_data)
    if rozbicie is not None:
        dane["parser_confidence"] = rozbicie.confidence
        dane["parser_alternatywy"] = rozbicie.alternatywy
    return dane
```

W `analizuj()` zbuduj `parser_ctx` RAZ i przekaż. Zamień pętlę:

```python
    mapowanie = parent.mapowanie_kolumn or {}
    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        if mapowanie:
            elem = remapuj_wiersz(elem, mapowanie)
        _przetworz_wiersz(parent, elem)
```

na:

```python
    mapowanie = parent.mapowanie_kolumn or {}
    parser_ctx = zbuduj_parser_kontekst()
    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        if mapowanie:
            elem = remapuj_wiersz(elem, mapowanie)
        _przetworz_wiersz(parent, elem, parser_ctx)
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_osoba.py -v`
Expected: PASS.

- [ ] **Step 5: Regresja analizy (parser_ctx opcjonalny nie psuje Fazy 0–2)**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/ -v`
Expected: PASS (istniejące testy analizy nadal zielone — buduje się teraz
`parser_ctx`, ale wiersze bez `osoba_sklejona` nie odpalają parsera).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze_osoba.py
git commit -m "feat(import_pracownikow): analiza rozbija osoba_sklejona parserem (Faza 3 T6)"
```

---

### Task 7: Pipeline analizy — status §8 zamiast twardego `XLSMatchError`

Zamiana: brak matcha przestaje rzucać. ID-path priorytet (przez `matchuj_autora`);
poza ID — `znajdz_kandydatow_autora` + `oblicz_status_pewnosci`. Zapis `confidence`,
kandydatów (`wielu`), autora dla `twardy`/`zgadywanie`. ID-konflikt `bpp_id` nadal
rzuca.

**Files:**
- Modify: `src/import_pracownikow/pipeline/analyze.py`
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze_status.py`

**Interfaces:**
- Consumes: `pewnosc.oblicz_status_pewnosci`, `pewnosc.wybierz_autora_z_kandydatow`,
  `pewnosc.STATUS_*` (Task 1); `import_common.core.autor.znajdz_kandydatow_autora`,
  `matchuj_autora`; `ImportPracownikowRowKandydat.zapisz_dla` (Task 2).
- Produces: `_przetworz_wiersz` ustawia `row.confidence`, zapisuje `row.kandydaci`
  dla `wielu`, `row.autor` dla `twardy`/`zgadywanie`, `None` dla `brak`/`wielu`;
  `zmiany_potrzebne=False` dla `brak`/`wielu`.

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_analyze_status.py`:

```python
from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_common.exceptions import XLSMatchError
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
)
from import_pracownikow.pipeline.analyze import analizuj


def _wiersz(**over):
    base = {
        "nazwisko": "Kowalski",
        "imię": "Jan",
        "nazwa_jednostki": "Katedra Testowa",
        "wydział": "Wydział Testowy",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    base.update(over)
    return base


def _analizuj_jeden(imp, wiersz):
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))
    return imp.importpracownikowrow_set.get()


@pytest.mark.django_db
def test_status_twardy_pojedynczy_exact():
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp, _wiersz(nazwisko="Kowalski", imię="Jan", nazwa_jednostki=jednostka.nazwa)
    )
    assert row.confidence == STATUS_TWARDY
    assert row.autor_id == autor.pk


@pytest.mark.django_db
def test_status_brak_nie_rzuca_i_nie_ustawia_autora():
    baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    # nazwisko nie istnieje w bazie → znajdz_kandydatow_autora zwraca []
    row = _analizuj_jeden(imp, _wiersz(nazwisko="Niematycki", imię="Zdzisław"))
    assert row.confidence == STATUS_BRAK
    assert row.autor is None
    assert row.zmiany_potrzebne is False


@pytest.mark.django_db
def test_status_wielu_zapisuje_kandydatow_bez_autora():
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    # DWÓCH autorów o identycznym imieniu+nazwisku → remis na najwyższym tierze
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp, _wiersz(nazwisko="Kowalski", imię="Jan", nazwa_jednostki=jednostka.nazwa)
    )
    assert row.confidence == STATUS_WIELU
    assert row.autor is None
    assert row.zmiany_potrzebne is False
    assert row.kandydaci.count() == 2


@pytest.mark.django_db
def test_status_twardy_po_bpp_id():
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    autor = baker.make(Autor, nazwisko="Zielinski", imiona="Adam")
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp,
        _wiersz(
            nazwisko="Zielinski",
            imię="Adam",
            nazwa_jednostki=jednostka.nazwa,
            bpp_id=str(autor.pk),
        ),
    )
    assert row.confidence == STATUS_TWARDY
    assert row.autor_id == autor.pk


@pytest.mark.django_db
def test_orcid_nieobecny_nie_wymusza_twardy_przy_remisie():
    # ORCID z pliku NIE istnieje w bazie → ID-path nie rozstrzyga. Dwóch
    # kandydatów po 1.0 w RÓŻNYCH jednostkach → remis top-tier → status WIELU.
    # Regresja F4: gdyby gałąź ID fallbackowała na jednostkę/nazwisko,
    # matchuj_autora rozstrzygnąłby remis jednostką z pliku → błędnie twardy.
    j1 = baker.make(Jednostka, nazwa="Jedn. A", skrot="J.A")
    j2 = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor_Jednostka, autor=a1, jednostka=j1)
    baker.make(Autor_Jednostka, autor=a2, jednostka=j2)
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp,
        _wiersz(
            nazwisko="Kowalski",
            imię="Jan",
            nazwa_jednostki=j2.nazwa,
            orcid="0000-0000-0000-9999",
        ),
    )
    assert row.confidence == STATUS_WIELU
    assert row.autor is None
    assert row.kandydaci.count() == 2


@pytest.mark.django_db
def test_konflikt_bpp_id_nadal_rzuca():
    # bpp_id w pliku wskazuje NIEISTNIEJĄCEGO autora, ale nazwisko+imię matchuje
    # kogoś innego → matchuj_autora (ID → None → fallback po nazwisku) zwraca
    # tego autora, a jego pk != bpp_id z pliku → twardy błąd (jak dziś).
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    nieistniejacy_bpp_id = autor.pk + 999999
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [
                _wiersz(
                    nazwisko="Kowalski",
                    imię="Jan",
                    nazwa_jednostki=jednostka.nazwa,
                    bpp_id=str(nieistniejacy_bpp_id),
                )
            ]
        )
        with pytest.raises(XLSMatchError):
            analizuj(imp, MockProgress(imp))
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_status.py -v`
Expected: FAIL (dziś `brak` rzuca `XLSMatchError`; `confidence`/`kandydaci` nie są
ustawiane).

- [ ] **Step 3: Przepisz sekcję autora w `_przetworz_wiersz`**

W `src/import_pracownikow/pipeline/analyze.py` dodaj importy (po
`import_pracownikow.parsers.osoba`):

```python
from import_common.core.autor import znajdz_kandydatow_autora
from import_pracownikow.models import ImportPracownikowRowKandydat
from import_pracownikow.pewnosc import (
    STATUS_TWARDY,
    STATUS_WIELU,
    oblicz_status_pewnosci,
    wybierz_autora_z_kandydatow,
)
```

(`ImportPracownikowRowKandydat` dodaj do istniejącego bloku importu z
`import_pracownikow.models`, jeśli wolisz — byle był zaimportowany.)

Dodaj helper (nad `_przetworz_wiersz`):

```python
def _dopasuj_autora_i_status(data, jednostka, tytul_str):
    """Zwraca (autor, status, kandydaci). ID-path (priorytet) dopasowuje
    WYŁĄCZNIE po identyfikatorach: ``imiona/nazwisko/jednostka/tytul_str`` są
    PRZEKAZANE JAKO None, żeby ``matchuj_autora`` nie odpalił swoich fallbacków
    nazwiskowych/jednostkowych (autor.py:577-600). Inaczej remis top-tier byłby
    rozstrzygnięty jednostką/tytułem i błędnie oznaczony jako ``twardy`` —
    łamiąc §8 (jednostka/tytuł to tylko tie-breakery preselekcji, nie status).
    Gdy ID nie rozstrzyga (None) — SPADAMY do ścieżki kandydatów. Poza ID —
    status WPROST z ``znajdz_kandydatow_autora``; ``autor`` tylko dla
    twardy/zgadywanie (przez wspólny ``wybierz_autora_z_kandydatow``)."""
    ma_id = any(
        data.get(k) not in (None, "")
        for k in ("bpp_id", "orcid", "pbn_uuid", "numer", "pbn_id")
    )
    if ma_id:
        autor_po_id = matchuj_autora(
            imiona=None,
            nazwisko=None,
            jednostka=None,
            bpp_id=data.get("bpp_id"),
            pbn_uid_id=data.get("pbn_uuid"),
            system_kadrowy_id=data.get("numer"),
            pbn_id=data.get("pbn_id"),
            orcid=data.get("orcid"),
            tytul_str=None,
        )
        if autor_po_id is not None:
            return autor_po_id, STATUS_TWARDY, []

    kandydaci = znajdz_kandydatow_autora(data.get("imię"), data.get("nazwisko"))
    status = oblicz_status_pewnosci(kandydaci, match_po_id=False)
    autor = wybierz_autora_z_kandydatow(kandydaci, status)
    return autor, status, kandydaci
```

Zamień istniejący blok matchowania autora + twardy błąd. Usuń:

```python
    autor = matchuj_autora(
        imiona=data.get("imię"),
        nazwisko=data.get("nazwisko"),
        jednostka=jednostka,
        bpp_id=data.get("bpp_id"),
        pbn_uid_id=data.get("pbn_uuid"),
        system_kadrowy_id=data.get("numer"),
        pbn_id=data.get("pbn_id"),
        orcid=data.get("orcid"),
        tytul_str=tytul_str,
    )
    if autor is None:
        raise XLSMatchError(elem, "autor", "brak dopasowania - różne kombinacje")
    if data.get("bpp_id") is not None and data.get("bpp_id") != autor.pk:
        raise XLSMatchError(
            elem,
            "autor",
            "BPP ID zmatchowanego autora i BPP ID w pliku XLS nie zgadzają się",
        )

    # Autor_Jednostka: dopasowanie bez tworzenia (dry-run).
    aj = Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).first()
    if aj is None:
        diff["autor_jednostka"] = {"autor": autor.pk, "jednostka": jednostka.pk}
```

i wstaw w to miejsce:

```python
    autor, status, kandydaci = _dopasuj_autora_i_status(data, jednostka, tytul_str)
    if (
        data.get("bpp_id") is not None
        and autor is not None
        and data.get("bpp_id") != autor.pk
    ):
        raise XLSMatchError(
            elem,
            "autor",
            "BPP ID zmatchowanego autora i BPP ID w pliku XLS nie zgadzają się",
        )

    # Autor_Jednostka: dopasowanie bez tworzenia (dry-run). Dla brak/wielu
    # (autor None) nie ma jak policzyć AJ — pomijamy.
    aj = None
    if autor is not None:
        aj = Autor_Jednostka.objects.filter(
            autor=autor, jednostka=jednostka
        ).first()
        if aj is None:
            diff["autor_jednostka"] = {"autor": autor.pk, "jednostka": jednostka.pk}
```

W konstruktorze `ImportPracownikowRow(...)` dodaj pole `confidence=status,`
(np. po `autor=autor,`).

Zamień blok ustawiania `zmiany_potrzebne` (dziś `if aj is not None: ... else:
row.zmiany_potrzebne = True`) na wariant uwzględniający brak autora:

```python
    if autor is None:
        # brak/wielu: nie ma co integrować dopóki user nie rozstrzygnie
        row.zmiany_potrzebne = False
    elif aj is not None:
        # bool(diff): wiersz z odroczonym create'em słownika MUSI trafić do
        # integracji, nawet gdy guard is-not-None wyzerował check.
        row.zmiany_potrzebne = bool(diff) or row.check_if_integration_needed()
    else:
        row.zmiany_potrzebne = True
    row.save()

    if status == STATUS_WIELU:
        ImportPracownikowRowKandydat.zapisz_dla(row, kandydaci)
```

(Usuń stare `row.save()` na końcu funkcji, żeby nie zapisać dwukrotnie — powyższy
blok kończy się `row.save()` przed zapisem kandydatów. `zapisz_dla` (classmethod,
Task 2) kasuje ewentualnych poprzednich kandydatów i robi `bulk_create` —
świeżo utworzony wiersz żadnych nie ma, więc delete jest no-opem.)

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_status.py -v`
Expected: PASS (6).

- [ ] **Step 5: Regresja całej analizy (matchowalne wiersze nadal twardy)**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/ src/import_pracownikow/tests/test_models/ -v`
Expected: PASS. Istniejące testy analizy (`dwa_autory_z_jednostka`,
`autor_bez_autor_jednostka`) matchują pojedynczego autora → `twardy` → `autor`
ustawiony jak dotąd; asercje o `diff_do_utworzenia`/`autor_jednostka` bez zmian.
Podaj liczbę passed.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze_status.py
git commit -m "feat(import_pracownikow): status pewności zamiast twardego błędu matcha (Faza 3 T7)"
```

---

### Task 8: Integracja — pomijanie brak/wielu-bez-wyboru + licznik

Wiersze `brak`/`wielu` bez autora mają `zmiany_potrzebne=False`, więc integracja
ich nie dotyka. Dodajemy do wyniku licznik pominiętych niedopasowanych +
ostrzeżenie.

**Files:**
- Modify: `src/import_pracownikow/pipeline/integrate.py`
- Test: `src/import_pracownikow/tests/test_pipeline/test_integrate_status.py`

**Interfaces:**
- Consumes: `pewnosc.STATUS_BRAK`, `STATUS_WIELU` (Task 1); `confidence`/`autor`
  na `ImportPracownikowRow` (Task 2/7).
- Produces: `integruj` wynik zawiera `pominieto_niedopasowane` (int) i
  `wymaga_uwagi` (bool).

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_integrate_status.py`:

```python
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_WIELU
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_integracja_liczy_pominiete_brak_i_wielu():
    imp = baker.make(
        ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY
    )
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    ImportPracownikowRow.objects.create(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_BRAK, autor=None
    )
    ImportPracownikowRow.objects.create(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_WIELU, autor=None
    )
    p = MockProgress(imp)
    integruj(imp, p)

    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
    assert p.result_context["pominieto_niedopasowane"] == 2
    assert p.result_context["wymaga_uwagi"] is True
    # nietknięte — dalej bez autora
    assert imp.importpracownikowrow_set.filter(autor__isnull=True).count() == 2
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate_status.py -v`
Expected: FAIL (`KeyError: 'pominieto_niedopasowane'`).

- [ ] **Step 3: Dodaj licznik do `integruj`**

W `src/import_pracownikow/pipeline/integrate.py` dodaj import (po istniejących):

```python
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_WIELU
```

W funkcji `integruj`, przed `p.result(...)`, dolicz niedopasowane i rozszerz wynik.
Zamień końcówkę:

```python
    p.result(
        {
            "zintegrowano": zintegrowano,
            "pominieto_nieaktualne": pominieto_nieaktualne,
            "stan": parent.stan,
        }
    )
```

na:

```python
    # Wiersze brak/wielu bez rozstrzygnięcia usera (autor None) — świadomie
    # pominięte w tej fazie (Faza 4 doda „utwórz nowego"). Raportujemy licznik
    # + flagę „wymaga uwagi", żeby podsumowanie nie udawało pełnego sukcesu.
    pominieto_niedopasowane = parent.importpracownikowrow_set.filter(
        confidence__in=[STATUS_BRAK, STATUS_WIELU], autor__isnull=True
    ).count()
    p.result(
        {
            "zintegrowano": zintegrowano,
            "pominieto_nieaktualne": pominieto_nieaktualne,
            "pominieto_niedopasowane": pominieto_niedopasowane,
            "wymaga_uwagi": pominieto_niedopasowane > 0,
            "stan": parent.stan,
        }
    )
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate_status.py -v`
Expected: PASS.

- [ ] **Step 5: Regresja integracji Fazy 0–2**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_integrate.py -v`
Expected: PASS (nowe klucze wyniku nie psują istniejących asercji).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/pipeline/integrate.py \
  src/import_pracownikow/tests/test_pipeline/test_integrate_status.py
git commit -m "feat(import_pracownikow): integracja raportuje pominięte brak/wielu (Faza 3 T8)"
```

---

### Task 9: Widok wyboru kandydata (POST `wybrany_kandydat`)

Owner-scoped POST: ustaw `wybrany_kandydat`, materializuj `row.autor`, przelicz
`zmiany_potrzebne`, zwróć wyrenderowany partial wiersza.

**Files:**
- Modify: `src/import_pracownikow/views.py`, `src/import_pracownikow/urls.py`
- Create: `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
  (minimalny — pełny render w T11)
- Test: `src/import_pracownikow/tests/test_views_wiersz.py`

**Interfaces:**
- Consumes: `ImportPracownikowRow`, `ImportPracownikowRowKandydat` (Task 2);
  `pewnosc.odtworz_autor_jednostka`, `pewnosc.STATUS_TWARDY` (Task 1);
  `GROUP_REQUIRED`.
- Produces: `WybierzKandydataView` (POST), URL name `wybierz-kandydata`
  (`<uuid:pk>/wiersz/<int:row_pk>/wybierz-kandydata/`). Po materializacji autora
  woła `odtworz_autor_jednostka(row, autor)`, który odtwarza `row.autor_jednostka`
  (+ `diff_do_utworzenia["autor_jednostka"]` gdy AJ nie istnieje) i ZDEJMUJE
  ewentualny nieaktualny wpis od poprzedniego autora — jak faza analizy — żeby
  integracja nie trafiła na `autor_jednostka=None` ani nie utworzyła AJ dla złego
  autora. `_WierszImportuMixin` wnosi bramkę stanu (POST tylko dla importu w
  stanie `przeanalizowany`) współdzieloną z `EdytujWierszView` (T10).

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_views_wiersz.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_TWARDY, STATUS_WIELU


def _wielu_row(owner):
    imp = baker.make(
        ImportPracownikow, owner=owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=1.0, powod="iexact"
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a2, pewnosc=1.0, powod="iexact"
    )
    return imp, row, a1


@pytest.mark.django_db
def test_wybor_kandydata_materializuje_autora(admin_client, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.wybrany_kandydat_id == a1.pk
    assert row.autor_id == a1.pk
    assert row.confidence == STATUS_TWARDY
    assert row.zmiany_potrzebne is True


@pytest.mark.django_db
def test_wybor_kandydata_odrzuca_obcego_autora(admin_client, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    obcy = baker.make(Autor, nazwisko="Obcy", imiona="Ktoś")
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": obcy.pk})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_wybor_kandydata_owner_scoped(client, django_user_model, admin_user):
    imp, row, a1 = _wielu_row(admin_user)
    inny = django_user_model.objects.create_user(
        username="inny", password="x", is_staff=True
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    inny.groups.add(grupa)
    client.force_login(inny)
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_wybor_kandydata_odrzucony_gdy_import_zintegrowany(admin_client, admin_user):
    # G3: bramka stanu — POST wyboru na wierszu importu już zintegrowanego
    # (retry HTMX / back-button / wyścig z Zatwierdź) MUSI dać 400 i NIE
    # nadpisać danych po commicie ani integrować drugi raz.
    imp, row, a1 = _wielu_row(admin_user)
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY
    imp.save(update_fields=["stan"])
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": a1.pk})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.autor is None


@pytest.mark.django_db
def test_odtworz_autor_jednostka_zdejmuje_wpis_i_odklada_create():
    # G1 (jednostkowy): stary diff AJ dla POPRZEDNIEGO autora zostaje zdjęty,
    # a dla nowego autora BEZ istniejącego AJ odkładany jest świeży create.
    from bpp.models import Autor, Jednostka
    from import_pracownikow.pewnosc import odtworz_autor_jednostka

    imp = baker.make(ImportPracownikow)
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    nowy = baker.make(Autor, nazwisko="Nowy", imiona="Jan")  # bez AJ
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=nowy,
        zmiany_potrzebne=True,
        dane_znormalizowane={},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    odtworz_autor_jednostka(row, nowy)
    assert row.autor_jednostka is None
    assert row.diff_do_utworzenia["autor_jednostka"]["autor"] == nowy.pk
    assert row.zmiany_potrzebne is True


@pytest.mark.django_db
def test_wybor_kandydata_nie_koruptuje_aj_starego_autora(admin_client, admin_user):
    # G1 (regresja korupcji): wiersz miał odłożony diff AJ dla STAREGO autora
    # (np. z wcześniejszej ścieżki analizy), a user wybiera NOWEGO kandydata,
    # który MA już Autor_Jednostka. Po wyborze uśpiony wpis starego autora musi
    # zniknąć — inaczej integracja utworzyłaby AJ dla starego i nadpisała
    # row.autor_jednostka (dane zatrudnienia nowego autora u starego).
    from bpp.models import Autor, Autor_Jednostka, Jednostka

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    nowy = baker.make(Autor, nazwisko="Nowy", imiona="Jan")
    aj_nowy = baker.make(Autor_Jednostka, autor=nowy, jednostka=jednostka)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=stary, pewnosc=1.0, powod="iexact"
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=nowy, pewnosc=1.0, powod="iexact"
    )
    url = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"wybrany_kandydat": nowy.pk})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor_id == nowy.pk
    assert "autor_jednostka" not in row.diff_do_utworzenia
    assert row.autor_jednostka_id == aj_nowy.pk
    # stary autor nie dostał żadnego AJ (nie było i nie powstało)
    assert not Autor_Jednostka.objects.filter(autor=stary).exists()
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_wiersz.py -v`
Expected: FAIL (brak URL/widoku).

- [ ] **Step 3: Widok + mixin + URL + partial**

W `src/import_pracownikow/views.py` dodaj importy (do istniejącego bloku
Django/braces):

```python
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views import View
```

**G2:** widok woła `get_object_or_404(ImportPracownikowRow, ...)`, a dziś `views.py`
importuje z `import_pracownikow.models` tylko `ImportPracownikow, ProfilMapowania`.
Rozszerz tę linię o `ImportPracownikowRow` (bez tego `NameError` przy pierwszym
requeście):

```python
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ProfilMapowania,
)
```

Dodaj mixin owner-scoped + widok wyboru (po `RestartAnalizaView` lub w sensownym
miejscu). Umieść PRZED `ImportPracownikowResultsView` klasę pomocniczą i widok:

```python
class _WierszImportuMixin(GroupRequiredMixin, View):
    """Wspólny fetch wiersza importu: owner/superuser-scoped parent + wiersz.
    Render partiala do odpowiedzi HTMX."""

    group_required = GROUP_REQUIRED
    partial_template = "import_pracownikow/partials/_wiersz_preview.html"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    @cached_property
    def row(self):
        return get_object_or_404(
            ImportPracownikowRow, pk=self.kwargs["row_pk"], parent=self.parent_object
        )

    def _blad_jesli_nie_podglad(self):
        """G3: wybór/edycja dozwolone WYŁĄCZNIE dla importu w podglądzie
        (``przeanalizowany``). Bez tej bramki bezpośredni POST (retry HTMX,
        back-button, wyścig z Zatwierdź) na wierszu importu już `zintegrowanego`
        nadpisałby audyt ``log_zmian`` po commicie i pozwolił zintegrować drugi
        raz. Analog `_STANY_MAPOWALNE`/`_STANY` — zintegrowany wykluczony. Zwraca
        ``HttpResponseBadRequest`` (blokada) albo ``None`` (OK)."""
        if self.parent_object.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Wiersz można edytować tylko dla importu w podglądzie."
            )
        return None

    def _render_wiersz(self):
        # Re-pobierz wiersz przez get_details_set(), żeby partial miał adnotacje
        # nr_arkusza/nr_wiersza (RawSQL) — inaczej te komórki byłyby puste po
        # swapie HTMX. Odzwierciedla zapisane właśnie zmiany.
        row = self.parent_object.get_details_set().get(pk=self.row.pk)
        return render(
            self.request,
            self.partial_template,
            {"row": row, "parent_object": self.parent_object},
        )


class WybierzKandydataView(_WierszImportuMixin):
    """POST: ustaw wybranego kandydata dla wiersza ``wielu`` → materializuj
    ``row.autor`` i przelicz ``zmiany_potrzebne``. Zwraca partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        try:
            wybrany_id = int(request.POST.get("wybrany_kandydat", ""))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Brak lub błędny wybrany_kandydat.")
        kandydat = row.kandydaci.filter(autor_id=wybrany_id).first()
        if kandydat is None:
            # Wybór musi być jednym z zapisanych kandydatów tego wiersza.
            return HttpResponseBadRequest("Autor nie jest kandydatem tego wiersza.")

        autor = kandydat.autor
        row.wybrany_kandydat = autor
        row.autor = autor
        row.confidence = STATUS_TWARDY

        # Materializacja autora MUSI odtworzyć powiązanie Autor_Jednostka tak
        # jak faza analizy (analyze._przetworz_wiersz) I zdjąć ewentualny
        # nieaktualny wpis diff od poprzedniego autora — inaczej integrate() →
        # _integrate_autor_jednostka() zrobi aj.save() na None (AttributeError)
        # albo utworzy AJ dla złego autora. `row.autor` jest ustawiony wyżej,
        # więc helper może bezpiecznie wołać check_if_integration_needed().
        odtworz_autor_jednostka(row, autor)
        row.save(
            update_fields=[
                "wybrany_kandydat",
                "autor",
                "confidence",
                "autor_jednostka",
                "diff_do_utworzenia",
                "zmiany_potrzebne",
            ]
        )
        return self._render_wiersz()
```

Dodaj import helpera + stałej statusu u góry `views.py` (helper mieszka w
`pewnosc.py` — to jedyne miejsce reguły AJ, współdzielone z T10; NIE importuj
`Autor_Jednostka` do widoków — sięga po nie helper):

```python
from import_pracownikow.pewnosc import STATUS_TWARDY, odtworz_autor_jednostka
```

W `src/import_pracownikow/urls.py` dodaj (po `restart-analiza`):

```python
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/wybierz-kandydata/",
        views.WybierzKandydataView.as_view(),
        name="wybierz-kandydata",
    ),
```

Utwórz minimalny partial
`src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
(pełny render w T11; teraz wystarczy poprawny fragment). Komentarze `{# #}`
jednoliniowe:

```django
{# Partial pojedynczego wiersza podglądu — zwracany po akcjach HTMX. #}
<tr id="wiersz-{{ row.pk }}">
    <td>{{ row.dane_znormalizowane.imię }}</td>
    <td>{{ row.dane_znormalizowane.nazwisko }}</td>
    <td>
        {% with badge=row.confidence_badge %}
            <span class="label {{ badge.0 }}">
                <i class="{{ badge.1 }}"></i> {{ badge.2 }}
            </span>
        {% endwith %}
    </td>
    <td>
        {% if row.autor %}
            <a href="{% url "bpp:browse_autor" row.autor.pk %}">{{ row.autor }}</a>
        {% else %}
            —
        {% endif %}
    </td>
</tr>
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_wiersz.py -v`
Expected: PASS (6: materializacja, obcy autor, owner-scope, bramka stanu G3,
helper jednostkowy G1, regresja korupcji AJ G1).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html \
  src/import_pracownikow/tests/test_views_wiersz.py
git commit -m "feat(import_pracownikow): widok wyboru kandydata (Faza 3 T9)"
```

---

### Task 10: Widok edycji inline (HTMX POST korekta)

POST z poprawionymi `imiona`/`nazwisko`/`tytul`: zapis do `korekta_uzytkownika`,
synchroniczny re-match (`znajdz_kandydatow_autora` + `oblicz_status_pewnosci`),
nadpisanie `confidence`/kandydatów/`autor`, zwrot partiala.

**Files:**
- Modify: `src/import_pracownikow/views.py`, `src/import_pracownikow/urls.py`
- Test: `src/import_pracownikow/tests/test_views_wiersz.py` (dopisz)

**Interfaces:**
- Consumes: `znajdz_kandydatow_autora`, `oblicz_status_pewnosci`,
  `pewnosc.wybierz_autora_z_kandydatow`, `pewnosc.odtworz_autor_jednostka`
  (Task 1), `ImportPracownikowRowKandydat.zapisz_dla` (Task 2),
  `_WierszImportuMixin` + jego bramka stanu (Task 9); `bpp.models.Tytul`.
- Produces: `EdytujWierszView` (POST, ta sama bramka stanu G3 co T9), URL name
  `edytuj-wiersz` (`<uuid:pk>/wiersz/<int:row_pk>/edytuj/`); helper
  `_rematch_wiersz(row, imiona, nazwisko, tytul)` — przelicza `row.tytul` (FK),
  a powiązanie AJ oddaje wspólnemu `odtworz_autor_jednostka` (autor≠None); dla
  `autor=None` ZDEJMUJE uśpiony wpis `diff_do_utworzenia["autor_jednostka"]` i
  zeruje AJ, po czym przelicza `zmiany_potrzebne`.

- [ ] **Step 1: Napisz failing test**

Dopisz do `src/import_pracownikow/tests/test_views_wiersz.py`:

```python
from import_pracownikow.pewnosc import STATUS_BRAK  # noqa: E402


@pytest.mark.django_db
def test_edycja_inline_rematchuje_i_zapisuje_korekte(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow, owner=admin_user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    # w bazie jest właściwy autor, ale wiersz startowo „brak" (błędne rozbicie)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Janx", "nazwisko": "Kowalskix"},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(
        url, {"imiona": "Jan", "nazwisko": "Kowalski", "tytul": ""}
    )
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.korekta_uzytkownika["nazwisko"] == "Kowalski"
    assert row.autor_id == autor.pk
    assert row.confidence == STATUS_TWARDY
    assert row.dane_znormalizowane["nazwisko"] == "Kowalski"


@pytest.mark.django_db
def test_edycja_inline_korekta_tytulu_ustawia_fk(admin_client, admin_user):
    # F6: korekta tytułu musi zaktualizować FK row.tytul (integracja czyta
    # row.tytul_id, nie JSON) — inaczej do bazy trafi stary tytuł.
    from bpp.models import Tytul

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    # Tytul.skrot/nazwa unique + baseline preloaduje „dr" → get_or_create.
    tytul = Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})[0]
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        tytul=None,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(
        url, {"imiona": "Jan", "nazwisko": "Kowalski", "tytul": "dr"}
    )
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.tytul_id == tytul.pk
    assert row.dane_znormalizowane["tytuł_stopień"] == "dr"


@pytest.mark.django_db
def test_edycja_inline_brak_zdejmuje_uspiony_wpis_aj(admin_client, admin_user):
    # G1 (ścieżka autor=None): wiersz miał odłożony diff AJ dla starego autora,
    # a korekta prowadzi do statusu „brak" (re-match nie znajduje nikogo) →
    # uśpiony wpis AJ MUSI zniknąć, inaczej integracja utworzyłaby AJ dla
    # już-nie-autora wiersza.
    from bpp.models import Autor, Jednostka

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    stary = baker.make(Autor, nazwisko="Stary", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=stary,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=True,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Stary"},
        diff_do_utworzenia={
            "autor_jednostka": {"autor": stary.pk, "jednostka": jednostka.pk}
        },
        log_zmian={"autor": [], "autor_jednostka": []},
    )
    url = reverse(
        "import_pracownikow:edytuj-wiersz",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(
        url, {"imiona": "Zdzisław", "nazwisko": "Nieistniejacy", "tytul": ""}
    )
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.autor is None
    assert row.confidence == STATUS_BRAK
    assert "autor_jednostka" not in row.diff_do_utworzenia
    assert row.autor_jednostka is None
    assert row.zmiany_potrzebne is False
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_wiersz.py -k edycja_inline -v`
Expected: FAIL (brak URL/widoku).

- [ ] **Step 3: Widok edycji + helper re-match + URL**

W `src/import_pracownikow/views.py` dodaj importy statusu/kandydatów (rozszerz
istniejące):

```python
from django.db.models import Q

from bpp.models import Tytul
from import_common.core.autor import znajdz_kandydatow_autora
from import_pracownikow.models import ImportPracownikowRowKandydat
from import_pracownikow.pewnosc import (
    STATUS_WIELU,
    oblicz_status_pewnosci,
    wybierz_autora_z_kandydatow,
)
```

(`STATUS_TWARDY` oraz `odtworz_autor_jednostka` są już zaimportowane w T9 — nie
duplikuj. `Autor_Jednostka` NIE jest importowane do `views.py` — sięga po nie
helper w `pewnosc.py`. `STATUS_ZGADYWANIE` niepotrzebny w T10, bo wybór autora
idzie przez wspólny `wybierz_autora_z_kandydatow`.)

Dodaj helper re-match i widok (po `WybierzKandydataView`):

```python
def _rematch_wiersz(row, imiona, nazwisko, tytul):
    """Ponawia dopasowanie autora dla skorygowanego wiersza (synchronicznie).
    Nadpisuje confidence/autor/kandydatów, tytuł (FK) i dane_znormalizowane;
    odtwarza Autor_Jednostka dla NOWEGO autora i przelicza zmiany_potrzebne.
    Ścieżka bez ID (korekta dotyczy rozbicia nazwiska)."""
    kandydaci = znajdz_kandydatow_autora(imiona, nazwisko)
    status = oblicz_status_pewnosci(kandydaci, match_po_id=False)
    autor = wybierz_autora_z_kandydatow(kandydaci, status)

    dane = dict(row.dane_znormalizowane or {})
    dane["imię"] = imiona
    dane["nazwisko"] = nazwisko
    if tytul:
        dane["tytuł_stopień"] = tytul
    else:
        dane.pop("tytuł_stopień", None)
    row.dane_znormalizowane = dane

    # Korekta tytułu MUSI trafić do FK row.tytul — integracja czyta row.tytul_id
    # (z analizy), nie JSON; bez tego do bazy poszedłby stary tytuł.
    # G4: filter().first() (nie .get()) — wejście od usera; ten sam string bywa
    # `nazwa` jednego tytułu i `skrot` innego (unique tylko osobno), więc .get()
    # rzuciłby MultipleObjectsReturned (500). None gdy brak dopasowania.
    if tytul:
        row.tytul = Tytul.objects.filter(Q(nazwa=tytul) | Q(skrot=tytul)).first()
    else:
        row.tytul = None

    row.korekta_uzytkownika = {
        "imiona": imiona,
        "nazwisko": nazwisko,
        "tytul": tytul,
    }
    row.confidence = status
    row.autor = autor
    row.wybrany_kandydat = None

    # Materializacja NOWEGO autora → PRZELICZ Autor_Jednostka od zera (nie ufaj
    # staremu row.autor_jednostka od poprzedniego autora) przez wspólny helper,
    # który ZAWSZE zdejmuje uśpiony wpis diff od poprzedniego autora. Bez AJ
    # integrate() → _integrate_autor_jednostka() zrobiłby aj.save() na None
    # (AttributeError). `row.autor` jest ustawiony wyżej.
    if autor is None:
        # brak/wielu po korekcie: też zdejmij uśpiony wpis AJ od poprzedniego
        # autora (inaczej integracja utworzy AJ dla już-nie-autora wiersza),
        # wyzeruj powiązanie, nic do integracji dopóki user nie rozstrzygnie.
        row.diff_do_utworzenia.pop("autor_jednostka", None)
        row.autor_jednostka = None
        row.zmiany_potrzebne = False
    else:
        odtworz_autor_jednostka(row, autor)

    row.save()
    # zapisz_dla kasuje starych kandydatów i wstawia nowych; dla nie-wielu
    # przekazujemy [] (tylko czyszczenie — wiersz zszedł z „wielu").
    ImportPracownikowRowKandydat.zapisz_dla(
        row, kandydaci if status == STATUS_WIELU else []
    )


class EdytujWierszView(_WierszImportuMixin):
    """POST (HTMX): korekta rozbicia imiona/nazwisko/tytuł → zapis
    ``korekta_uzytkownika`` + synchroniczny re-match → partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        imiona = (request.POST.get("imiona") or "").strip()
        nazwisko = (request.POST.get("nazwisko") or "").strip()
        tytul = (request.POST.get("tytul") or "").strip()
        if not nazwisko:
            return HttpResponseBadRequest("Nazwisko jest wymagane.")
        _rematch_wiersz(row, imiona, nazwisko, tytul)
        return self._render_wiersz()
```

**Uwaga (dlaczego odtwarzamy AJ przez wspólny helper, a nie tylko liczymy flagę):**
`row.check_if_integration_needed()` sięga `_check_autor_jednostka_needs_update`,
które czyta `self.autor_jednostka`. Gdyby zostało `None` (materializowany autor
bez AJ), `check` rzuciłby `AttributeError`, a integracja później też — bo
`_integrate_autor_jednostka` robi `aj.save()` na `None`. Dlatego dla autora≠None
delegujemy do `pewnosc.odtworz_autor_jednostka`, który ODTWARZA `autor_jednostka`
dokładnie jak faza analizy: gdy AJ (autor, jednostka) istnieje → podpina je (i
`check_if_integration_needed()` działa bezpiecznie); gdy nie istnieje → odkłada
create w `diff_do_utworzenia["autor_jednostka"]` (integracja materializuje przez
`get_or_create`) i ustawia `zmiany_potrzebne=True`. **Kluczowe (G1):** helper
ZAWSZE najpierw `diff_do_utworzenia.pop("autor_jednostka", None)`, więc uśpiony
wpis od POPRZEDNIEGO autora nie przetrwa zmiany autora — inaczej integracja
utworzyłaby AJ dla złego autora. W gałęzi `autor=None` helpera nie wołamy, ale
robimy ten sam `pop` ręcznie. To ta sama reguła AJ co w T9 (współdzielony helper)
i T7 (inline) — nie pomijaj jej.

W `src/import_pracownikow/urls.py` dodaj (po `wybierz-kandydata`):

```python
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/edytuj/",
        views.EdytujWierszView.as_view(),
        name="edytuj-wiersz",
    ),
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_wiersz.py -v`
Expected: PASS (9: 6 z T9 + korekta/rematch, korekta tytułu FK, zdjęcie uśpionego
wpisu AJ w ścieżce brak G1).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/urls.py \
  src/import_pracownikow/tests/test_views_wiersz.py
git commit -m "feat(import_pracownikow): edycja inline wiersza z re-matchem (Faza 3 T10)"
```

---

### Task 11: Podgląd — kolumny rozbicia, badge, dropdown kandydatów, edycja inline

Rozszerz szablon podglądu: kolumny imiona/nazwisko/tytuł + badge confidence,
sort non-twardy na górę, dropdown kandydatów dla `wielu` (HTMX POST), formularz
edycji inline (HTMX POST). Ikony = Foundation-Icons; badge = Foundation labels.

**Files:**
- Modify: `src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`
- Modify: `src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
  (pełny render kontrolek)
- Modify: `src/import_pracownikow/views.py` (`ImportPracownikowResultsView.get_queryset`
  — sort non-twardy na górę)
- Test: `src/import_pracownikow/tests/test_views_preview_render.py`
- Modify: `src/import_pracownikow/tests/test_views_liveops.py` (regresja audytu
  „Lista modyfikacji" + ewentualna aktualizacja asercji — patrz Step 5/6)

**Interfaces:**
- Consumes: `row.confidence_badge` (Task 2), `row.kandydaci`, URL-e
  `wybierz-kandydata`/`edytuj-wiersz` (Task 9/10), `pewnosc.STATUS_TWARDY`.
- Produces: podgląd renderuje kontrolki tylko w stanie `przeanalizowany`.

- [ ] **Step 1: Napisz failing test**

Utwórz `src/import_pracownikow/tests/test_views_preview_render.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_TWARDY, STATUS_WIELU


@pytest.mark.django_db
def test_podglad_pokazuje_badge_i_dropdown_kandydatow(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 7},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=1.0, powod="iexact"
    )
    url = reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}
    )
    resp = admin_client.get(url)
    tresc = resp.content.decode("utf-8")
    assert resp.status_code == 200
    # KONKRETNY badge statusu „wielu" (Foundation label primary + ikona +
    # etykieta) — nie samo „label"/„fi-", które przeciekają z base.html.
    assert "label primary" in tresc
    assert "fi-page-multiple" in tresc
    assert "wielu kandydatów" in tresc
    # dropdown kandydatów dla wielu (HTMX POST na wybierz-kandydata)
    assert reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    ) in tresc


@pytest.mark.django_db
def test_podglad_sortuje_nie_twardy_na_gore(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Zz", imiona="Aa")
    twardy = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=autor,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=True,
        dane_znormalizowane={},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    wielu = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 9},
    )
    from import_pracownikow.views import ImportPracownikowResultsView

    view = ImportPracownikowResultsView()
    view.kwargs = {"pk": imp.pk}
    view.request = type("R", (), {"user": admin_user})()
    lista = list(view.get_queryset())
    # non-twardy (wielu) mimo wyższego nr wiersza jest PRZED twardym
    assert lista[0].pk == wielu.pk
    assert lista[1].pk == twardy.pk
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py -v`
Expected: FAIL (podgląd nie renderuje kontrolek; brak sortu).

- [ ] **Step 3: Sort w `get_queryset`**

W `src/import_pracownikow/views.py` dodaj importy (do bloku Django db). `Prefetch`
domyka N+1 dropdownu kandydatów (G5); `ImportPracownikowRowKandydat` jest już
zaimportowane w T10 — nie duplikuj:

```python
from django.db.models import Case, IntegerField, Prefetch, Value, When
```

W `ImportPracownikowResultsView` dodaj `get_queryset` (nadpisuje bazowy —
`get_details_set()` już annotuje `nr_arkusza`/`nr_wiersza`):

```python
    def get_queryset(self):
        # non-twardy (do rozstrzygnięcia) na górę, potem kolejność z pliku.
        # G5: prefetch kandydatów Z AUTOREM — partial dla wierszy `wielu` iteruje
        # row.kandydaci.all i czyta k.autor per opcja dropdownu; bez tego N+1
        # (setki zapytań przy dużych plikach).
        return (
            self.parent_object.get_details_set()
            .annotate(
                _prio=Case(
                    When(confidence=STATUS_TWARDY, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .prefetch_related(
                Prefetch(
                    "kandydaci",
                    queryset=ImportPracownikowRowKandydat.objects.select_related(
                        "autor"
                    ),
                )
            )
            .order_by("_prio", "nr_arkusza", "nr_wiersza")
        )
```

- [ ] **Step 4: Pełny partial `_wiersz_preview.html`**

Nadpisz
`src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html`
(komentarze `{# #}` jednoliniowe; Foundation-Icons; HTMX). Renderuje tę samą
strukturę `<tr>` co include w liście, żeby swap outerHTML był spójny:

```django
{# Partial pojedynczego wiersza podglądu — include w liście oraz zwracany #}
{# po akcjach HTMX (wybór kandydata / edycja inline). #}
<tr id="wiersz-{{ row.pk }}">
    <td>{{ row.nr_arkusza }}</td>
    <td>{{ row.nr_wiersza }}</td>
    <td>{{ row.dane_znormalizowane.imię }}</td>
    <td>{{ row.dane_znormalizowane.nazwisko }}</td>
    <td>{{ row.dane_znormalizowane.tytuł_stopień }}</td>
    <td>
        {% with badge=row.confidence_badge %}
            <span class="label {{ badge.0 }}">
                <i class="{{ badge.1 }}"></i> {{ badge.2 }}
            </span>
        {% endwith %}
    </td>
    <td>
        {% if row.autor %}
            <a href="{% url "bpp:browse_autor" row.autor.pk %}">{{ row.autor }}</a>
        {% else %}
            —
        {% endif %}
    </td>
    <td>
        {% if parent_object.stan == "przeanalizowany" %}
            {% if row.confidence == "wielu" %}
                {# dropdown kandydatów — POST ustawia wybrany_kandydat #}
                <form method="post"
                      hx-post="{% url "import_pracownikow:wybierz-kandydata" pk=parent_object.pk row_pk=row.pk %}"
                      hx-target="#wiersz-{{ row.pk }}"
                      hx-swap="outerHTML">
                    {% csrf_token %}
                    <select name="wybrany_kandydat">
                        {% for k in row.kandydaci.all %}
                            <option value="{{ k.autor.pk }}">
                                {{ k.autor }} ({{ k.pewnosc }})
                            </option>
                        {% endfor %}
                    </select>
                    <button type="submit" class="button tiny">
                        <i class="fi-check"></i> wybierz
                    </button>
                </form>
            {% endif %}
            {# korekta rozbicia — POST ponawia match wiersza #}
            <form method="post"
                  hx-post="{% url "import_pracownikow:edytuj-wiersz" pk=parent_object.pk row_pk=row.pk %}"
                  hx-target="#wiersz-{{ row.pk }}"
                  hx-swap="outerHTML">
                {% csrf_token %}
                <input type="text" name="imiona"
                       value="{{ row.dane_znormalizowane.imię }}"
                       placeholder="imiona">
                <input type="text" name="nazwisko"
                       value="{{ row.dane_znormalizowane.nazwisko }}"
                       placeholder="nazwisko">
                <input type="text" name="tytul"
                       value="{{ row.dane_znormalizowane.tytuł_stopień }}"
                       placeholder="tytuł">
                <button type="submit" class="button tiny secondary">
                    <i class="fi-refresh"></i> popraw
                </button>
            </form>
        {% else %}
            {# Poza stanem „przeanalizowany" (np. „zintegrowany") pokazujemy #}
            {# audyt zmian — to JEDYNY widok log_zmian dla stanu po integracji. #}
            {% for elem in row.sformatowany_log_zmian %}
                <p>{{ elem }}</p>
            {% endfor %}
        {% endif %}
    </td>
</tr>
```

- [ ] **Step 5: Rozszerz szablon listy o kolumny rozbicia i include partiala**

Nadpisz blok `content` w
`src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html`.
Zachowaj sekcję `autorzy_spoza_pliku` (na dole) BEZ ZMIAN — testy `test_views.py`
zależą od jej tekstu. Zmień tylko tabelę wierszy i jej gate. Wczytaj HTMX (jak
`importer_publikacji/index.html`). Cały plik:

```django
{% extends "base.html" %}{% load render_table from django_tables2 %}

{% block extratitle %}
    Import pracowników - szczegóły {{ parent_object.plik_xls.name }}
{% endblock %}

{% block breadcrumbs %}
    {{ block.super }}
    <li><a href="{% url "import_pracownikow:index" %}">import pracowników</a></li>
    <li class="current">import {{ parent_object.plik_xls.name }}</li>
{% endblock %}


{% block content %}
    <h1>Import danych {{ parent_object.plik_xls.name }}</h1>

    {# HTMX dla akcji per-wiersz (wybór kandydata / edycja inline) — patrz #}
    {# wzorzec importer_publikacji/index.html. #}
    <script src="https://unpkg.com/htmx.org@2.0.4" crossorigin="anonymous"></script>

    {% if parent_object.finished_successfully %}
        {# Nagłówek audytu — asertowany przez test_views_liveops.py; NIE usuwać. #}
        <p>Lista modyfikacji do bazy danych, przeprowadzonych na podstawie
            pliku XLS poniżej:</p>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>Arkusz</th>
                        <th>Wiersz</th>
                        <th>Imiona</th>
                        <th>Nazwisko</th>
                        <th>Tytuł</th>
                        <th>Pewność</th>
                        <th>Autor</th>
                        <th>Akcje / zmiany</th>
                    </tr>
                </thead>
                <tbody>
                    {% include "pagination.html" %}
                    {% for row in object_list %}
                        {% include "import_pracownikow/partials/_wiersz_preview.html" %}
                        {% empty %}
                        <tr>
                            <td colspan="8" class="text-center"><strong>
                                Żadnych wierszy do pokazania.
                            </strong></td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    {% endif %}


    {% if autorzy_spoza_pliku.exists %}
        <h4>Na podstawie tego pliku importu należałoby odpiąć
            {{ autorzy_spoza_pliku.count }} powiązań autor+jednostka, oto one ponizej: </h4>
        <a data-confirm="Czy na pewno?" href="../resetuj-podstawowe-miejsce-pracy/">Kliknij tutaj, żeby przypisać. Uwaga, to zmieni bazę dancyh. </a>
        <table>
            <tr>
                <th>Autor</th>
                <th>Jednostka</th>
            </tr>
            {% for elem in autorzy_spoza_pliku %}
                <tr>
                    <td>{{ elem.autor }}</td>
                    <td>{{ elem.jednostka }}</td>
                </tr>
            {% endfor %}
        </table>
    {% else %}
        <h4>Zawartość tego pliku nie powoduje konieczności "likwidowania" podstawowych miejsc
            pracy dla autorów w bazie. </h4>
    {% endif %}

{% endblock %}
```

- [ ] **Step 6: Uruchom testy — zielone (w tym regresja audytu)**

Run: `uv run pytest src/import_pracownikow/tests/test_views_preview_render.py src/import_pracownikow/tests/test_views.py src/import_pracownikow/tests/test_views_liveops.py -v`
Expected: PASS (nowe render/sort + istniejące `test_views.py` — sekcja
`autorzy_spoza_pliku` nietknięta; wiersze integrated mają `autor` ustawiony i
`confidence` None → badge neutralny, `stan==zintegrowany` → brak kontrolek,
kolumna zmian renderuje `sformatowany_log_zmian`). `test_views_liveops.py`
(`test_importpracownikow_results_renderuje_liste_modyfikacji`, `STAN_ZINTEGROWANY`)
MUSI dalej znajdować „Lista modyfikacji" i `plik_xls.name` — nagłówek audytu i
kolumna log-u zmian zostały zachowane w przepisanym szablonie (F3). Jeśli jednak
zmieniłeś tekst nagłówka/kolumny, ZAKTUALIZUJ asercję w tym teście w tym kroku
(nie odkładaj do T12).

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html \
  src/import_pracownikow/templates/import_pracownikow/partials/_wiersz_preview.html \
  src/import_pracownikow/views.py \
  src/import_pracownikow/tests/test_views_preview_render.py
git commit -m "feat(import_pracownikow): podgląd — badge, kandydaci, edycja inline (Faza 3 T11)"
```

---

### Task 12: E2E + newsfragment

Pełny przepływ Fazy 3 przez ekran: upload kolumny `osoba_sklejona` → mapowanie →
analiza (eager) → statusy → wybór kandydata → integracja.

**Files:**
- Create: `src/import_pracownikow/tests/test_pipeline/test_faza3_e2e.py`
- Create: `src/bpp/newsfragments/import-pracownikow-parser-pewnosc.feature.rst`

**Interfaces:**
- Consumes: cały przepływ Fazy 3 (mapowanie osoba_sklejona → analiza → wybór →
  integracja).

- [ ] **Step 1: Napisz test e2e**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_faza3_e2e.py`:

```python
"""E2E Fazy 3: plik z kolumną sklejonej osoby + statusy pewności + wybór
kandydata. LIVEOPS.RUNNER='eager' (settings/test.py) → enqueue() wykonuje run()
synchronicznie w ramach POST-a."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pewnosc import STATUS_TWARDY, STATUS_WIELU


@pytest.mark.django_db
def test_e2e_osoba_sklejona_status_i_wybor(admin_client, admin_user):
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    # Tytul.skrot/nazwa unique + baseline preloaduje „dr/doktor" → get_or_create.
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})
    # jeden jednoznaczny (twardy) + dwóch o identycznym imieniu (wielu)
    twardy = baker.make(
        Autor, nazwisko="Zielinski", imiona="Adam", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=twardy, jednostka=jednostka)
    dup1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")

    csv = (
        "Osoba;Nazwa jednostki\n"
        f"dr Adam Zielinski;{jednostka.nazwa}\n"
        f"dr Jan Kowalski;{jednostka.nazwa}\n"
    ).encode("utf-8")
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    # mapowanie: Osoba → osoba_sklejona; analiza rusza eager w POST-cie
    url_map = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url_map,
        {
            "kol__osoba": "osoba_sklejona",
            "kol__nazwa_jednostki": "nazwa_jednostki",
            "zapisz_profil": False,
            "nazwa_profilu": "",
        },
    )
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY

    wiersze = {r.dane_znormalizowane["nazwisko"]: r for r in imp.importpracownikowrow_set.all()}
    assert wiersze["Zielinski"].confidence == STATUS_TWARDY
    assert wiersze["Zielinski"].autor_id == twardy.pk
    assert wiersze["Kowalski"].confidence == STATUS_WIELU
    assert wiersze["Kowalski"].autor is None
    assert wiersze["Kowalski"].kandydaci.count() == 2

    # wybór kandydata dla wiersza „wielu"
    url_wybor = reverse(
        "import_pracownikow:wybierz-kandydata",
        kwargs={"pk": imp.pk, "row_pk": wiersze["Kowalski"].pk},
    )
    resp = admin_client.post(url_wybor, {"wybrany_kandydat": dup1.pk})
    assert resp.status_code == 200
    wiersze["Kowalski"].refresh_from_db()
    assert wiersze["Kowalski"].autor_id == dup1.pk
    assert wiersze["Kowalski"].zmiany_potrzebne is True

    # zatwierdź → integracja (eager); brak/wielu bez wyboru pominięte (tu 0)
    url_zatw = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    resp = admin_client.post(url_zatw)
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY

    # F1: wybór kandydata dup1 odtworzył powiązanie AJ (diff_do_utworzenia), więc
    # integracja UTWORZYŁA Autor_Jednostka (dup1, jednostka) i NIE rzuciła
    # AttributeError w _integrate_autor_jednostka.
    assert Autor_Jednostka.objects.filter(autor=dup1, jednostka=jednostka).exists()
```

- [ ] **Step 2: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_faza3_e2e.py -v`
Expected: PASS.

- [ ] **Step 3: Newsfragment**

Utwórz `src/bpp/newsfragments/import-pracownikow-parser-pewnosc.feature.rst`:

```rst
Import pracowników rozbija teraz sklejoną komórkę „tytuł/imię/nazwisko" na
składniki i pokazuje **pewność dopasowania** każdego autora (twardy match /
zgadywanie / wielu kandydatów / brak). Niepewne wiersze można poprawić w
podglądzie: skorygować rozbicie nazwiska albo wybrać właściwego kandydata z
listy — bez ponownego wgrywania pliku.
```

- [ ] **Step 4: Pełna regresja Fazy 0+1+2+3**

Run: `uv run pytest src/import_pracownikow/ src/import_common/ -q`
Expected: PASS wszystko. Podaj liczbę passed/failed.

- [ ] **Step 5: Ruff + pinned format**

Run: `uv run ruff check src/import_pracownikow/`
oraz `uv run pre-commit run ruff-format --files $(git diff --name-only $(git merge-base dev HEAD) | tr '\n' ' ')`
Expected: czyste (dołącz zmiany formatera do commita).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/tests/test_pipeline/test_faza3_e2e.py \
  src/bpp/newsfragments/import-pracownikow-parser-pewnosc.feature.rst
git commit -m "test(import_pracownikow): e2e Fazy 3 + newsfragment (Faza 3 T12)"
```

---

## Nota o baseline (przy MERGE, nie na tym branchu)

Migracja `0013_confidence_kandydaci` zmienia schemat (`ImportPracownikowRow` +
nowy model kandydata). Odświeżenie baseline (`make baseline-update`) robimy
**dopiero przy scalaniu** gałęzi do `dev` — NIE na feature-branchu (reguła
CLAUDE.md: równoległe branch'e nie mogą kolidować na jednym pliku `baseline.sql`).
Commituj wtedy oba: `baseline-sql/baseline.sql` + `baseline-sql/baseline.meta.json`.

---

## Self-Review (autor planu)

**Spec coverage §7 (parser):**
- Rdzeń czysty bez ORM + wstrzykiwany `probuj_match`/słowniki → T3 (`osoba.py`) ✅
- Longest-match tytułów z obu stron (fraza wieloczłonowa) → T3 `_zdejmij_tytuly`
  + przypadek „prof. dr hab. n. med." ✅
- Sygnały kolejności: przecinek/WERSALIKI/match-do-bazy/leksykon/dywiz/fallback →
  T3 (tabelaryczne przypadki a–l) ✅
- Wiele imion = wszystkie nie-nazwiskowe tokeny → T3 case „dr hab. Anna Maria
  Nowak" ✅
- `alternatywy` przy słabym sygnale → T3 `test_low_confidence_ma_alternatywe` ✅
- Adapter wstrzykuje realne `tytuly`/`imiona_znane`/`probuj_match` z bazy → T4 ✅
- Parser uruchamiany TYLKO gdy zmapowana `osoba_sklejona` → T5 (cel mapowania) +
  T6 (wstrzyknięcie w pipeline gdy `dane_form.get("osoba_sklejona")`) ✅
- `osoba_sklejona` dodane do `POLA_DOCELOWE` (nie było w Fazie 2) → T5 ✅
- confidence rozbicia + alternatywy w `dane_znormalizowane` (nie kolumna) → T6
  `_dane_znormalizowane_z_parserem` ✅

**Spec coverage §8 (status pewności):**
- Status liczony WPROST z `znajdz_kandydatow_autora`, nie z `matchuj_autora`
  (poza ID) → T7 `_dopasuj_autora_i_status` + T1 `oblicz_status_pewnosci` ✅
- 4 statusy + reguła „czystego zwycięzcy" (remis→wielu) + próg → T1 (7 testów) ✅
- Priorytet ścieżki po ID → T7 (`ma_id` → `matchuj_autora` → twardy) ✅
- Konflikt `bpp_id` twardy błąd → T7 `test_konflikt_bpp_id_nadal_rzuca` ✅
- `brak`/`wielu` nie są błędem; autor None; kandydaci zapisani (wielu) →
  T7 (testy brak/wielu) ✅
- Nowa kolumna `confidence` (choices STATUS_*) + model
  `ImportPracownikowRowKandydat` (wzorzec `ImportedAuthor_Candidate`) → T2 ✅
- Pola decyzji usera `wybrany_kandydat` + `korekta_uzytkownika` → T2 (migracja),
  materializacja przy `wielu` → T9; `utworz_nowego`/tworzenie autora = Faza 4
  (poza zakresem) ✅
- Edycja inline HTMX (korekta → re-match → partial) → T10; wybór kandydata (POST
  → materializacja autora → przelicz zmiany_potrzebne) → T9 ✅
- Integracja pomija brak/wielu-bez-wyboru + licznik/ostrzeżenie → T8 ✅
- UI: badge kolory przez Foundation labels + Foundation-Icons (NIE emoji),
  sort non-twardy na górę, dropdown kandydatów, formularz edycji → T11 ✅

**Placeholder scan:** brak TBD/TODO/„similar to"; każdy krok z pełnym kodem
(test i implementacja). Partial `_wiersz_preview.html` tworzony minimalnie w T9,
rozwijany do pełni w T11 — oba kroki mają kompletny kod (nie placeholder).

**Type/signature consistency:**
- `oblicz_status_pewnosci(kandydaci, *, match_po_id) -> str` — spójne T1/T7/T10.
- `wybierz_autora_z_kandydatow(kandydaci, status) -> Autor | None` (F10) — jedno
  źródło reguły „autor = kandydaci[0].autor dla twardy/zgadywanie" w
  `pewnosc.py` (T1), użyte w analizie (T7 `_dopasuj_autora_i_status`) i re-matchu
  inline (T10 `_rematch_wiersz`).
- `ImportPracownikowRowKandydat.zapisz_dla(row, kandydaci) -> None` (F10,
  classmethod) — jedno źródło zapisu kandydatów (delete-all + bulk_create), użyte
  w T7 (analiza) i T10 (re-match; `[]` = tylko czyszczenie).
- Odtworzenie `autor_jednostka`/`diff_do_utworzenia["autor_jednostka"]` po
  materializacji autora (F1) — ta sama reguła w analizie (T7), wyborze kandydata
  (T9) i re-matchu inline (T10); bez niej `integrate()` rzuca AttributeError.
- `STATUS_TWARDY/ZGADYWANIE/WIELU/BRAK` + `STATUS_CHOICES`/`STATUS_DISPLAY` —
  jedno źródło (`pewnosc.py`), import w modelu (T2), pipeline (T7/T8), widokach
  (T9/T10), szablonie (przez `confidence_badge`).
- `WynikRozbicia(tytul, imiona, nazwisko, confidence, alternatywy)` +
  `rozbij_osobe(tekst, *, tytuly, imiona_znane, probuj_match)` — spójne T3/T4/T6.
- `ParserKontekst(tytuly, imiona_znane, probuj_match)` — T4 produkuje, T6
  konsumuje.
- `ImportPracownikowRowKandydat(row, autor, pewnosc, powod, publikacji_count)` —
  T2 definiuje (+ classmethod `zapisz_dla`), T7/T10 zapisują przez `zapisz_dla`,
  T9/T11 czytają (`row.kandydaci`).
- `_przetworz_wiersz(parent, elem, parser_ctx=None)` — T6 rozszerza sygnaturę
  (backward compat), T7 dokłada logikę bez zmiany sygnatury.
- URL names `wybierz-kandydata`/`edytuj-wiersz` + partial `_wiersz_preview.html`
  spójne T9/T10/T11/T12.

**Backward compat:** nowe pola nullable/default (T2); parser odpalany tylko gdy
`osoba_sklejona` (T6); status zastępuje twardy błąd, ale matchowalne wiersze dają
`twardy` z ustawionym `autor` (regresja T7 Step 5); sekcja `autorzy_spoza_pliku`
w szablonie nietknięta (regresja T11 Step 6). Jedna nowa migracja `0013`; baseline
przy merge.
