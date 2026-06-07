# PBN Import — rozdzielenie pobierania od przetwarzania

**Data:** 2026-06-07
**Branch:** `feature/pbn-import-rozdziel-pobieranie` (od `feature/multi-hosted-config`)
**Status:** Design — do akceptacji przed implementacją

---

## 1. Cel

W obecnym imporcie PBN każdy krok (np. „Źródła") wykonuje w jednym
przebiegu **dwie różne operacje**:

1. **Pobranie** danych z API PBN do lokalnych tabel-luster (`pbn_api.*`).
2. **Przetworzenie** (integrację) tych luster do modeli BPP (`bpp.*`).

Użytkownik chce móc uruchamiać te dwie operacje **niezależnie** — samo
pobieranie, samo przetwarzanie, albo oba. Powody operacyjne:

- pobranie jest powolne i zależne od API PBN; raz pobrane dane chcemy móc
  przetwarzać wielokrotnie bez ponownego ruchu sieciowego,
- przy debugowaniu integracji chcemy iterować na przetwarzaniu bez
  czekania na re-download,
- czasem chcemy tylko odświeżyć lustro (pobranie) bez dotykania danych BPP.

Docelowy UX: w formularzu konfiguracji importu **dwie kolumny** —
z lewej „Pobieranie", z prawej „Przetwarzanie" — z niezależnymi
checkboxami per encja.

## 2. Stan obecny (jak to działa dziś)

### 2.1. Pojedyncze źródło prawdy o krokach

`src/pbn_import/utils/step_definitions.py` zawiera `ALL_STEP_DEFINITIONS`
— listę słowników, każdy opisuje jeden krok:

```python
{
    "name": "source_import",
    "display": "Import źródeł",
    "class": SourceImporter,
    "disable_key": "disable_zrodla",
    "form_field": "zrodla",
    "icon": "fi-book",
    "required": False,
    "show_in_form": True,
}
```

Helpery czytane przez resztę systemu:

- `get_form_steps()` → dane dla checkboxów formularza (HTML),
- `get_command_steps()` → pary `(form_field, display)` dla CLI,
- `get_all_disable_keys()` → mapa `form_field → disable_key`,
- `get_step_definitions(config)` → lista kroków do wykonania,
  odfiltrowana po `disable_key` (krok pominięty, gdy
  `config[disable_key]` jest prawdziwe),
- `_get_step_args(step_name, config)` → dynamiczne argumenty kroku.

### 2.2. Wykonanie kroku

Każdy importer dziedziczy po `ImportStepBase`
(`src/pbn_import/utils/base.py`) i implementuje `run()`.
`ImportStepBase.__call__()` woła `start()` → `run()` → `finish()`.

`ImportManager` (`src/pbn_import/utils/import_manager.py`):

- w `__init__` buduje `self.steps = get_step_definitions(self.config)`,
- `_run_import_steps()` iteruje po krokach; `_execute_step()`
  instancjonuje klasę kroku z `**step_config["args"]` i ją woła.

### 2.3. Wewnętrzna struktura kroków (kluczowe)

Każdy `pobierz_*` z `pbn_integrator` zapisuje surowy JSON PBN do tabel
lustrzanych (`pbn_api.Journal`, `Publisher`, `Scientist`, `Publication`,
`OswiadczenieInstytucji`, `Conference`). Każdy `integruj_*` / `importuj_*`
czyta lustro i tworzy/aktualizuje modele BPP. **Pobranie persystuje w
DB**, więc przetwarzanie może działać później, niezależnie.

Klasyfikacja faz per krok (po analizie kodu):

| Krok (`name`) | Pobieranie | Przetwarzanie | Uwagi |
|---|---|---|---|
| `initial_setup` | — | — | wymagany, fazy wymieszane → **poza zakresem**, bez zmian |
| `institution_setup` | — | — | wymagany setup → **bez zmian** |
| `source_import` | `pobierz_zrodla_mnisw` | `importuj_zrodla` | **rozdzielany** |
| `source_scoring_import` | — | (cały) | **process-only**, działa na cache `pbn_uid`; bez zmian |
| `publisher_import` | `pobierz_wydawcow_mnisw` | `importuj_wydawcow` | **rozdzielany** |
| `conference_import` | `pobierz_konferencje` | **NOWY** `integruj_konferencje` | **rozdzielany** (patrz §5) |
| `author_import` | `pobierz_ludzi_z_uczelni` | `integruj_autorow_z_uczelni` | **rozdzielany** |
| `publication_import` | `_download_publications` + `_v2` | `_import_publications` | **rozdzielany** |
| `statement_import` | `pobierz_oswiadczenia_z_instytucji` | `_download_missing_publications` + `integruj_oswiadczenia_z_instytucji` | **rozdzielany** |
| `fee_import` | — | — | `get_publication_fees_batch` pobiera i zapisuje do BPP w tej samej pętli → **nierozdzielalny**, bez zmian |

**Sześć kroków rozdzielanych:** Źródła, Wydawcy, Konferencje, Autorzy,
Publikacje, Oświadczenia.

### 2.4. Konfiguracja jest płaska (JSONField)

`ImportSession.config` to `JSONField`. Konwencja: `config["disable_<x>"]`
= `True` oznacza „pomiń krok". Brak migracji DB przy zmianie kształtu
configu.

- **Formularz** (`dashboard.html`, `StartImportView.post`): checkbox
  `name="{form_field}"`; zaznaczony = NIE wyłączaj. Kod:
  `disable_key: not request.POST.get(form_field)`.
- **CLI** (`management/commands/pbn_import.py`): flagi
  `--disable-{form_field}`; `build_config_from_options` mapuje na
  `disable_key`.
- **Presety** (`ImportPresetsView`): słowniki gotowych zestawów
  `disable_*`.

## 3. Decyzje projektowe (ustalone z użytkownikiem)

1. **Zakres:** rozdzielamy wszystkie kroki, gdzie ma to sens (6 wyżej).
   `initial_setup` NIE rozbijamy wewnętrznie.
2. **Model UI:** dwa checkboxy na wiersz (Pobieranie | Przetwarzanie).
3. **Brak danych przy samym przetwarzaniu:** **miękkie ostrzeżenie** —
   `process()` loguje `warning` i kontynuuje (przetworzy 0 rekordów),
   bez twardego błędu i bez walidacji blokującej w formularzu.
4. **Zgodność wsteczna:** stary klucz `disable_<encja>` = obie podfazy;
   nowe klucze granularne nadpisują, gdy obecne. Stare presety, sesje
   i skrypty CLI działają bez zmian.
5. **Konferencje:** dodajemy brakującą integrację (nowy kod, §5).

## 4. Projekt techniczny

### 4.1. Model fazy w `step_definitions.py`

Każdy wpis `ALL_STEP_DEFINITIONS` zyskuje listę `phases`. Faza opisuje
jedną wykonywalną jednostkę:

```python
{
    "phase": "download",          # "download" | "process" | "single"
    "method": "download",          # nazwa metody na klasie kroku
    "form_field": "zrodla_download",
    "disable_key": "disable_zrodla_download",
    "display": "Źródła — pobieranie",
    "column": "download",          # "download" | "process" | "both"
    "legacy_key": "disable_zrodla",# stary klucz-alias (lub None)
}
```

- Krok **rozdzielany** ma dwie fazy: `download` (column=download) i
  `process` (column=process), obie z `legacy_key="disable_<encja>"`.
- Krok **niepodzielny** (`initial_setup`, `institution_setup`,
  `fee_import`) ma jedną fazę `single` (method=`run`, column=`both`),
  z `disable_key` = dotychczasowym kluczem (bez `_download`/`_process`).
- `source_scoring_import` → jedna faza `process` (column=process),
  method=`run`, klucz bez zmian (`disable_punktacja_zrodel`).

Konwencja nazw kluczy granularnych:
`disable_<encja>_download`, `disable_<encja>_process` dla:
`zrodla`, `wydawcy`, `konferencje`, `autorzy`, `publikacje`,
`oswiadczenia`.

Funkcje pomocnicze przepisane na fazy (zachowują nazwy i kontrakt
zewnętrzny, ale operują na płaskiej liście faz):

- `get_form_steps()` → struktura zgrupowana per encja, z polami
  `column`, `form_field`, `display`, `required` dla każdej fazy
  (formularz renderuje tabelę dwukolumnową — patrz §4.4).
- `get_command_steps()` → pary `(form_field, display)` dla **każdej
  fazy** (CLI dostaje granularne flagi) **plus** legacy aliasy (§4.5).
- `get_all_disable_keys()` → mapa wszystkich `form_field → disable_key`
  (granularnych).
- `get_step_definitions(config)` → **płaska, uporządkowana lista faz do
  wykonania** (patrz §4.3).

### 4.2. Klasy importerów — dwie metody (Opcja A)

Nie tworzymy osobnych klas per faza. `ImportStepBase` zyskuje:

```python
def download(self):
    """Faza pobierania — nadpisz w podklasie rozdzielanej."""
    raise NotImplementedError

def process(self):
    """Faza przetwarzania — nadpisz w podklasie rozdzielanej."""
    raise NotImplementedError

def run(self):
    """Domyślnie: obie fazy po kolei (zgodność wsteczna)."""
    # podklasy rozdzielane dziedziczą ten run(); niepodzielne nadpisują
    self.download()
    self.process()
```

`__call__` przyjmuje nazwę metody:

```python
def __call__(self, method: str = "run"):
    self.start()
    try:
        result = getattr(self, method)()
        self.finish()
        return result
    except Exception as e:
        self.handle_error(e, f"Krytyczny błąd w {self.step_name}")
        raise
```

Refaktor sześciu importerów rozdzielanych — `run()` rozbity na
`download()` + `process()`; istniejące metody prywatne reużyte:

- **SourceImporter:** `download()` = `pobierz_zrodla_mnisw`;
  `process()` = `importuj_zrodla`.
- **PublisherImporter:** `download()` = `pobierz_wydawcow_mnisw`;
  `process()` = `importuj_wydawcow`.
- **AuthorImporter:** `download()` = `pobierz_ludzi_z_uczelni`;
  `process()` = `integruj_autorow_z_uczelni`. (Setup uczelni potrzebny w
  obu — wspólny helper wywoływany w każdej fazie.)
- **PublicationImporter:** `download()` = `_setup_…` +
  `_download_publications` + `_download_publications_v2`;
  `process()` = `_setup_…` + (opcjonalny `_delete_existing_publications`,
  gdy `delete_existing`) + `_import_publications`.
  Uwaga: `delete_existing` jest operacją po stronie BPP → należy do
  `process()`.
- **StatementImporter:** `download()` = `pobierz_oswiadczenia_z_instytucji`;
  `process()` = `_setup_…` + `_download_missing_publications` +
  `integruj_oswiadczenia_z_instytucji`.
  Uwaga: `_download_missing_publications` to dociąg brakujących publikacji
  sterowany tym, czego brakuje w BPP względem już-pobranych oświadczeń —
  jest częścią integracji, więc klasyfikujemy go jako `process`.
- **ConferenceImporter:** `download()` = `pobierz_konferencje`;
  `process()` = **nowa** `integruj_konferencje` (§5).

Importery niepodzielne (`InitialSetup`, `InstitutionImporter`,
`FeeImporter`) i `SourceScoringImporter` **zostawiają `run()`** bez zmian;
nie dostają `download()`/`process()`.

### 4.3. ImportManager — wykonanie per faza

`get_step_definitions(config)` zwraca płaską listę pozycji do wykonania,
zachowując **kolejność**: dla kroku rozdzielanego najpierw `download`,
potem `process`; kolejność kroków jak w `ALL_STEP_DEFINITIONS`. Czyli
realna kolejność wykonania to: download Źródeł → process Źródeł →
download Wydawców → process Wydawców → … (semantyka jak dziś — każda
encja pobiera i przetwarza po sobie). Dwukolumnowy UI to grupowanie
**wizualne**, nie kolejność wykonania.

Każda pozycja niesie `method` (`download`/`process`/`run`). Manager:

```python
step = step_class(session=…, client=…, uczelnia=…, **args)
result = step(method=phase["method"])
```

Klucz wyniku w `results` musi być unikalny per faza, np.
`"source_import:download"` / `"source_import:process"`, żeby `results`
nie nadpisywał się między fazami tej samej encji.

Reszta `ImportManager` (autoryzacja, anulowanie, obsługa błędów,
`_run_post_import_commands`, refresh klienta po `initial_setup`) działa
bez zmian — operuje na `step_config["name"]`, który zostaje nazwą
**kroku** (nie fazy); fazę trzymamy w osobnym polu.

### 4.4. Formularz (dashboard.html + StartImportView)

Renderujemy **tabelę** zamiast płaskiej listy checkboxów:

```
                         Pobieranie     Przetwarzanie
 Konfiguracja początk.   [ wymagane — pełna szerokość, 1 checkbox ]
 Konfiguracja jednostek  [ wymagane — pełna szerokość, 1 checkbox ]
 Źródła                      [x]             [x]
 Punktacja źródeł             —              [x]
 Wydawcy                     [x]             [x]
 Konferencje                 [x]             [x]
 Autorzy                     [x]             [x]
 Publikacje                  [x]             [x]
 Oświadczenia                [x]             [x]
 Opłaty                   [ nierozdzielne — pełna szerokość, 1 checkbox ]
```

- Komórka z checkboxem: `name="{phase.form_field}"`, domyślnie `checked`.
- Komórka pusta (faza nie istnieje): renderujemy „—".
- Kroki niepodzielne (`initial_setup`, `institution_setup`,
  `fee_import`): jeden checkbox `name="{single.form_field}"` w wierszu
  rozciągniętym na obie kolumny (osobna grupa „Operacje niepodzielne"
  albo wiersz `colspan=2`).
- `StartImportView.post`: bez zmian co do logiki — iteruje po
  `get_all_disable_keys()` i ustawia `disable_key = not POST.get(form_field)`
  dla **każdej fazy**. Dochodzą tylko nowe `form_field`.
- JS presetów (dashboard.html, sekcja ~355–370): obecnie ustawia
  wszystkie checkboxy `checked`, potem odznacza te, których `disable_xxx`
  jest `True`. Logika działa dalej dla kluczy granularnych; dla
  zgodności wstecznej JS dodatkowo: jeśli preset niesie stary
  `disable_<encja>`, zastosuj go do obu checkboxów encji
  (`{encja}_download` i `{encja}_process`).

Styl: zwykła tabela Foundation (`<table>`), checkboxy bez nadpisywania
klas gridu. Ikony Foundation jak dziś (frontend publiczny/admin-mixed —
to widok importu w panelu, ikony `fi-*` zostają).

### 4.5. CLI (`management/commands/pbn_import.py`)

- Dla każdej fazy generujemy flagę `--disable-{phase.form_field}`
  (np. `--disable-zrodla-download`, `--disable-zrodla-process`).
- **Legacy alias:** zostają flagi `--disable-{encja}` (np.
  `--disable-zrodla`); gdy podana, ustawia obie podfazy encji na
  wyłączone. Implementacja: po sparsowaniu, w `build_config_from_options`,
  jeśli legacy flaga `True`, ustaw `disable_<encja>_download = True` i
  `disable_<encja>_process = True` (o ile granularna nie ustawiona
  jawnie).
- Menu interaktywne (`run_interactive`): lista wyboru pokazuje fazy jako
  osobne pozycje, pogrupowane czytelnie, np.
  „Źródła — pobieranie", „Źródła — przetwarzanie".

### 4.6. Rozwiązywanie configu — zgodność wsteczna

Centralna funkcja (w `step_definitions.py`) ustala, czy faza jest
wyłączona, w kolejności:

1. jeśli `config` zawiera klucz granularny fazy (`disable_<encja>_<faza>`)
   → użyj go,
2. wpp. jeśli `config` zawiera `legacy_key` (`disable_<encja>`)
   → użyj go (dotyczy obu faz encji),
3. wpp. faza włączona (domyślnie `not disabled`).

`get_step_definitions(config)` używa tej funkcji do filtrowania. Dzięki
temu:
- stare sesje/presety z `disable_zrodla=False` → pobranie i
  przetwarzanie Źródeł włączone (jak dziś),
- stare CLI `--disable-zrodla` → obie fazy pominięte,
- nowy formularz/CLI z kluczami granularnymi → pełna kontrola.

### 4.7. Miękkie ostrzeżenie przy pustym lustrze

Każda metoda `process()` rozdzielanego kroku na starcie sprawdza, czy
jej tabela lustrzana ma rekordy; jeśli pusta, loguje `warning` i
kontynuuje (istniejące pętle i tak przejdą po 0 rekordach):

| Krok | sprawdzane lustro |
|---|---|
| source | `pbn_api.Journal` |
| publisher | `pbn_api.Publisher` |
| author | `pbn_api.Scientist` |
| publication | `pbn_api.Publication` |
| statement | `pbn_api.OswiadczenieInstytucji` |
| conference | `pbn_api.Conference` |

Komunikat: „Brak pobranych danych dla kroku X — przetwarzam to, co jest
w lokalnym lustrze (0 rekordów). Uruchom fazę pobierania, jeśli to nie
zamierzone." Bez `error`, bez przerwania importu.

## 5. Nowa integracja konferencji

### 5.1. Stan obecny

- `pobierz_konferencje` (`pbn_integrator/utils/conferences.py`) pobiera
  konferencje do lustra `pbn_api.Conference`.
- Lustro `Conference` udostępnia: `fullName()`, `startDate()`,
  `endDate()`, `city()`, `country()`, `website` (widoczne w
  `pbn_api/admin/conference.py`).
- BPP **ma** model `bpp.models.Konferencja` (`src/bpp/models/konferencja.py`)
  z FK `pbn_uid → pbn_api.Conference`, polami `nazwa`, `skrocona_nazwa`,
  `rozpoczecie`, `zakonczenie`, `miasto`, `panstwo`, `typ_konferencji`,
  `baza_scopus/wos/inna`, oraz `unique_together = ("nazwa", "rozpoczecie")`.
- **Brak** funkcji `integruj_konferencje` — konferencje nie są dziś
  mapowane do BPP (metadane lądują tylko w `adnotacje` publikacji).

### 5.2. Nowa funkcja `integruj_konferencje`

Lokalizacja: `pbn_integrator/utils/conferences.py` (obok
`pobierz_konferencje`), spójnie z `importuj_zrodla`/`importuj_wydawcow`.

Sygnatura (wzorowana na innych integratorach):

```python
def integruj_konferencje(callback=None):
    """Integruj lustro pbn_api.Conference → bpp.Konferencja.

    Re-entrant: dopasowuje najpierw po pbn_uid, potem po
    (nazwa, rozpoczecie). Aktualizuje pola z PBN, nie nadpisuje
    danych BPP, których PBN nie dostarcza (typ_konferencji, bazy).
    """
```

Mapowanie pól:

| `pbn_api.Conference` | `bpp.Konferencja` | uwagi |
|---|---|---|
| obiekt lustra | `pbn_uid` | FK |
| `fullName()` | `nazwa` | wymagane; pomiń rekord, gdy puste + log warning |
| `startDate()` | `rozpoczecie` | parse ISO `YYYY-MM-DD`; `None` gdy brak/niepoprawny |
| `endDate()` | `zakonczenie` | jw. |
| `city()` | `miasto` | |
| `country()` | `panstwo` | |
| `value("object","abbreviation")` *(jeśli klucz istnieje)* | `skrocona_nazwa` | best-effort |

Pola **nieustawiane** (PBN nie dostarcza jednoznacznie):
`typ_konferencji`, `baza_scopus`, `baza_wos`, `baza_inna` — zostawiamy
wartości BPP (lub domyślne przy tworzeniu).

Logika dopasowania (idempotencja):

1. Konferencja z `pbn_uid == <to lustro>` istnieje → aktualizuj pola PBN.
2. Wpp. spróbuj dopasować po `unique_together (nazwa, rozpoczecie)` →
   jeśli istnieje rekord bez `pbn_uid` (wprowadzony ręcznie), **dowiąż**
   `pbn_uid` i zaktualizuj pola.
3. Wpp. utwórz nową `Konferencja`.

Pomijamy rekordy lustra ze `status == "DELETED"` (analogicznie do
istniejących integratorów — log `info`, bez tworzenia).

Obsługa błędów: parsowanie dat w `try/except` na wąskim `ValueError`
(niepoprawny format → `None` + log `debug`), zgodnie z regułą projektu
(brak gołych `except: pass`). Postęp przez `callback` jak w innych
krokach.

### 5.3. `ConferenceImporter.process()`

```python
def process(self):
    if not Conference.objects.exists():
        self.log("warning", "Brak pobranych konferencji — przetwarzam 0…")
    cb = self.create_subtask_progress("Integracja konferencji")
    try:
        wynik = integruj_konferencje(callback=cb)
        self.log("success", f"Zintegrowano {wynik} konferencji")
    except Exception as e:
        self.handle_error(e, "Nie udało się zintegrować konferencji")
    finally:
        self.clear_subtask_progress()
    return {"conferences_integrated": True, "error_count": len(self.errors)}
```

`download()` = dotychczasowa treść `run()` (samo `pobierz_konferencje`).

## 6. Pliki do zmiany / utworzenia

**Zmiana:**

- `src/pbn_import/utils/step_definitions.py` — model `phases`, przepisane
  helpery, funkcja rozwiązywania configu (§4.1, §4.6).
- `src/pbn_import/utils/base.py` — `download()`/`process()`/`run()` +
  `__call__(method=…)` (§4.2).
- `src/pbn_import/utils/import_manager.py` — wykonanie per faza,
  unikalne klucze `results` (§4.3).
- `src/pbn_import/utils/source_import.py` — split (§4.2).
- `src/pbn_import/utils/publisher_import.py` — split.
- `src/pbn_import/utils/author_import.py` — split.
- `src/pbn_import/utils/publication_import.py` — split (delete_existing
  po stronie process).
- `src/pbn_import/utils/statement_import.py` — split.
- `src/pbn_import/utils/conference_import.py` — split + wywołanie nowej
  integracji (§5.3).
- `src/pbn_integrator/utils/conferences.py` — **nowa**
  `integruj_konferencje` (§5.2).
- `src/pbn_import/templates/pbn_import/dashboard.html` — tabela
  dwukolumnowa + JS presetów (§4.4).
- `src/pbn_import/views.py` — `ImportPresetsView` (granularne klucze;
  legacy honorowane przez resolver) — drobne.
- `src/pbn_import/management/commands/pbn_import.py` — flagi granularne +
  legacy aliasy + menu (§4.5).

**Bez zmian (świadomie):** `initial_setup.py`, `institution_import.py`,
`fee_import.py`, `source_scoring_import.py`, modele
(`pbn_import/models.py`), migracje.

## 7. Testy

Pakiet: `src/pbn_import/tests/` (pytest, bez `unittest.TestCase`,
`model_bakery`, `@pytest.mark.django_db`).

**Nowe / rozszerzone:**

- `test_step_definitions.py`: model `phases`; `get_step_definitions`
  zwraca poprawną płaską listę i kolejność (download przed process per
  encja); resolver zgodności wstecznej (granularny vs legacy vs domyślny)
  — tabela przypadków.
- `test_importer_wrappers.py` / `test_step_constructor_contract.py`:
  `__call__(method=…)` woła właściwą metodę; `run()` woła obie;
  niepodzielne kroki nadal działają przez `run`.
- Split per importer: dla każdego z 6 — `download()` woła `pobierz_*` i
  NIE woła integracji; `process()` woła integrację i NIE woła `pobierz_*`
  (mock `pbn_integrator`); miękkie ostrzeżenie przy pustym lustrze.
- `test_import_manager.py`: sesja z samym pobieraniem; sama integracja;
  oba; klucze `results` unikalne per faza.
- **`integruj_konferencje`** (nowy plik testu, np.
  `test_conference_integration.py`): tworzenie z lustra, idempotencja po
  `pbn_uid`, dowiązanie istniejącego rekordu po `(nazwa, rozpoczecie)`,
  parsowanie/braki dat, pominięcie `DELETED`, mapowanie pól.
- `test_command_pbn_import.py`: flagi granularne; legacy alias
  `--disable-zrodla` wyłącza obie fazy.
- Render formularza: `get_form_steps` daje strukturę dwukolumnową;
  smoke-test widoku dashboard (kontekst `import_steps`).

**Regresja:** istniejące testy używające `disable_zrodla` itd. oraz
`SourceImporter().run()` mają przechodzić bez zmian (zgodność wsteczna).

Uruchomienie lokalnie (zgodnie z CLAUDE.md):

```bash
uv run pytest src/pbn_import/tests/
uv run pytest src/pbn_integrator/  # testy integracji konferencji
```

## 8. Ryzyka i uwagi

- **Kolejność wykonania** pozostaje per-encja (download→process danej
  encji), nie „wszystkie pobrania, potem wszystkie integracje". To
  świadome — zachowuje obecną semantykę i zależności (np. publikacje
  przed oświadczeniami). Dwukolumnowy UI jest czysto wizualny.
- **`results` keys**: zmiana z `name` na `name:phase` może dotykać
  konsumentów `results` (`_display_results` w CLI, ewentualne odczyty w
  widokach). Przejrzeć i dostosować wyświetlanie.
- **`abbreviation` konferencji**: klucz niepotwierdzony w API (admin go
  nie pokazuje). Mapujemy best-effort — tylko gdy obecny; brak nie jest
  błędem.
- **PublicationImporter.process** wymaga `default_jednostka` /
  `default_jezyk` (setup uczelni). Setup jest idempotentny i tani, więc
  wołamy go w obu fazach niezależnie — to umożliwia samodzielny
  `process` później.
- **Brak migracji DB** — `config` to JSONField; stare rekordy czytane
  przez resolver zgodności wstecznej.
