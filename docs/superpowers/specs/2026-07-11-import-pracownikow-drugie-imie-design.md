# Import pracowników — pole „Drugie imię"

**Data:** 2026-07-11
**Status:** zatwierdzony do implementacji
**Obszar:** `src/import_pracownikow/`

## Problem

Część plików kadrowych trzyma imiona w dwóch osobnych kolumnach: „Imię"
i „Drugie imię" (np. „Jan" | „Paweł"). Obecny import pracowników zna tylko
jeden cel mapowania na imię (`imię` → `AutorForm.imię` → `Autor.imiona`).
Kolumna „Drugie imię" nie ma dokąd trafić — mapuje się na `__pomin__`
i drugie imię przepada.

## Cel

Dodać cel mapowania **„Drugie imię"**, tak by pliki z rozbiciem imion na
dwie kolumny nie gubiły drugiego imienia. Przy przetwarzaniu wiersza drugie
imię jest **sklejane** z pierwszym w jedno pole `Autor.imiona`
(np. „Jan" + „Paweł" → „Jan Paweł").

**Bez zmian modelu i bez migracji** — `Autor` ma jedno pole `imiona`
(`CharField(max_length=512)`) na wszystkie imiona; nie wprowadzamy osobnego
`drugie_imie` w bazie. Decyzja użytkownika (brainstorm 2026-07-11).

## Kontekst techniczny (jak jest teraz)

Przepływ jednego wiersza w fazie analizy
(`import_pracownikow/pipeline/analyze.py::_przetworz_wiersz`):

1. `dane_form = normalizuj_wartosci_wiersza(elem)` — kopia wiersza po
   remapowaniu kolumn (`remapuj_wiersz`), z znormalizowanymi datami. Klucze to
   pola kanoniczne, np. `imię`, `nazwisko`, `nazwa_jednostki`.
2. `rozbicie = _rozbij_osoba_sklejona(dane_form, parser_ctx)` — jeśli jest
   kolumna `osoba_sklejona`, parser rozbija ją i **uzupełnia** `imię`/
   `nazwisko`/`tytuł_stopień`, ale tylko gdy dane pole jest jeszcze puste
   (`if not dane_form.get("imię")`).
3. `AutorForm(data=dane_form)` — walidacja. Django form czyta z `data`
   **wyłącznie** klucze odpowiadające zadeklarowanym polom; nadmiarowe klucze
   są ignorowane. `AutorForm` ma pola `nazwisko`, `imię`, `numer`, `orcid`,
   `tytuł_stopień`, … — **nie** ma `drugie_imię`.
4. `dane_znormalizowane = _dane_znormalizowane_z_parserem(
   autor_form.cleaned_data, rozbicie)` — kopia `cleaned_data` wzbogacona o
   `parser_confidence`/`parser_alternatywy` (gdy było rozbicie osoby
   sklejonej). To jest jedyne źródło prawdy o imieniu/nazwisku dla całej
   reszty pipeline'u; kluczowe: `imię` bierze się z `cleaned_data`.

Dwa fakty, które czynią zmianę bezpieczną i minimalną:

- **Cały downstream czyta `dane_znormalizowane["imię"]`** — matching autora
  (`_dopasuj_autora_i_status` → `znajdz_kandydatow_autora(data.get("imię"),
  …)`), tworzenie nowego autora (`integrate.py::_przygotuj_nowego_autora`,
  `imiona = dane.get("imię")`), a nawet korekta wiersza
  (`views.py::_rematch_wiersz` zapisuje `dane["imię"] = imiona`). Skoro
  scalimy przed zbudowaniem `AutorForm`, `cleaned_data["imię"]` = „Jan Paweł"
  i wszystkie te ścieżki dostają scaloną wartość **bez dotykania**.
- **Scalenie nie psuje dopasowania.** `znajdz_kandydatow_autora` stosuje
  m.in. `_strategia_iexact_pierwsze_imie` (pewność 0.95) — dopasowanie po
  **pierwszym** imieniu. Więc `imiona = "Jan Paweł"` nadal zmatchuje
  istniejącego w bazie „Jan Kowalski". Merge nie zrywa deduplikacji względem
  autorów, którzy mają zapisane tylko pierwsze imię.

Ekran mapowania (`MapowanieForm`) generuje pole `ChoiceField` per nagłówek
pliku, a listę wyborów bierze z `POLA_DOCELOWE` — dodanie nowego celu do tej
listy wystarcza, template nie wymaga zmian. Detekcja nagłówka pliku
(`TRY_NAMES`) liczy się z `_SYNONIMY.keys()` — dodanie synonimów automatycznie
rozszerza wykrywanie kolumn.

## Rozwiązanie

Trzy pliki produkcyjne + testy + changelog.

### 1. `src/import_pracownikow/mapping.py` — nowy cel mapowania

- `POLA_DOCELOWE`: dodać `("drugie_imię", "Drugie imię")` **tuż po**
  `("imię", "Imię")`.
- `_SYNONIMY`: dodać warianty znormalizowanych nagłówków → `"drugie_imię"`:
  - `"drugie_imię"`, `"drugie_imie"` (kanoniczne warianty z/bez ogonka),
  - `"drugie_imiona"`,
  - `"imię_drugie"`, `"imie_drugie"`.

  (Świadomie **bez** samodzielnego `"drugie"` — trafiłby do `TRY_NAMES` i
  podniósł ryzyko fałszywej detekcji wiersza nagłówka / złego auto-mapowania
  kolumny „Drugie" o innym znaczeniu. Powyższe warianty pokrywają praktykę.)

  (Normalizacja nagłówka `normalize_cell_header` robi lower + spacje/kropki/
  myślniki → `_`, więc „Drugie imię" → `drugie_imię`, „Drugie Imie" →
  `drugie_imie`.)
- `_POLA_IDENTYFIKACJI` — **bez zmian**. `drugie_imię` jest opcjonalne i
  **nie** identyfikuje osoby; nie może sam spełnić wymogu identyfikacji.
  Konsekwencja: zmapowanie samego „Drugie imię" bez „Imię" wywali istniejącą
  walidację `waliduj_mapowanie` („zmapuj nazwisko + imię albo osoba") —
  co jest pożądane. Guard na duplikaty w `waliduj_mapowanie` działa
  generycznie (obejmie też podwójne `drugie_imię`).

Nazwa klucza z ogonkiem (`drugie_imię`) jest spójna z konwencją modułu
(`imię`, `tytuł_stopień`, `wydział`, `data_końca_zatrudnienia`).

### 2. `src/import_pracownikow/parsers/wartosci.py` — helper scalający

Nowa, czysta funkcja (bez ORM, bez side-effectów poza mutacją wejścia):

```python
def sklej_drugie_imie(dane: dict) -> dict:
    """Scala kolumnę ``drugie_imię`` z ``imię`` w jedno pole (Autor ma jedno
    ``imiona``). Mutuje i zwraca ``dane``. Po scaleniu usuwa klucz
    ``drugie_imię`` — ``AutorForm`` go nie zna, a downstream czyta tylko
    ``imię``. ``str(...)`` bo XLSX (openpyxl) potrafi dać komórkę liczbową —
    ``.strip()`` na ``int`` rzuciłby ``AttributeError`` ubijający analizę."""
    drugie = str(dane.get("drugie_imię") or "").strip()
    if drugie:
        pierwsze = str(dane.get("imię") or "").strip()
        dane["imię"] = f"{pierwsze} {drugie}".strip()
    dane.pop("drugie_imię", None)
    return dane
```

Semantyka:

| `imię` (wejście) | `drugie_imię` | `imię` (wynik) |
|---|---|---|
| „Jan" | „Paweł" | „Jan Paweł" |
| „Jan" | „" / brak | „Jan" (klucz `drugie_imię` usunięty) |
| „" / brak | „Paweł" | „Paweł" (wiodąca spacja przycięta) |
| „Jan Anna" | „Maria" | „Jan Anna Maria" |

Pusty/brak `drugie_imię` → `imię` nietknięte, tylko usuwamy zbędny klucz.

### 3. `src/import_pracownikow/pipeline/analyze.py` — wpięcie scalania

W `_przetworz_wiersz`, **po** rozbiciu osoby sklejonej, a przed budową
`AutorForm`:

```python
dane_form = normalizuj_wartosci_wiersza(elem)
rozbicie = _rozbij_osoba_sklejona(dane_form, parser_ctx)
sklej_drugie_imie(dane_form)            # ← nowa linia
```

Import: `from import_pracownikow.parsers.wartosci import
normalizuj_wartosci_wiersza, sklej_drugie_imie` (dopisać do istniejącego
importu).

**Kolejność ma znaczenie — scalać PO `_rozbij_osoba_sklejona`.** Parser osoby
sklejonej uzupełnia `imię` tylko gdy jest ono puste (`analyze.py:114`,
`if not dane_form.get("imię")`). Gdyby scalać *przed* rozbiciem, plik mapujący
`osoba_sklejona` + `drugie_imię` **bez** kolumny `imię` (walidacja to
przepuszcza ścieżką „osoba") zachowałby się źle: `sklej` ustawiłoby
`imię = "Paweł"`, parser zobaczyłby niepuste `imię` i **nie** wstawiłby
imienia z rozbicia „Jan Kowalski" → wynik „Paweł" zamiast „Jan Paweł".
Scalanie *po* rozbiciu daje poprawny wynik we wszystkich układach kolumn
(rozbicie i tak nie nadpisuje niepustego `imię`).

### Czego NIE ruszamy

- `AutorForm` — `drugie_imię` scalane **przed** formularzem, więc formularz
  zostaje nietknięty (patrz „Kontekst techniczny", fakt o Django forms).
- `MapowanieForm` / template mapowania — pola generowane z `POLA_DOCELOWE`.
- `remapuj_wiersz` — generyczne przepisywanie kluczy; scalanie robimy poziom
  wyżej, w analizie (dwie kolumny → dwa różne cele → scalenie po remapie).
- `views.py::_rematch_wiersz` / `EdytujWierszView` — edytują już scalone
  `imiona`.
- `pipeline/integrate.py`, model `Autor`, migracje, profile mapowania
  (`ProfilMapowania.mapowanie` to JSON — nowy klucz nie wymaga migracji).

## Testy

Konwencja pytest (funkcje, `baker.make`, `@pytest.mark.django_db` gdy DB).

### `src/import_pracownikow/tests/test_mapping.py`
- `drugie_imię` obecne w `POLA_DOCELOWE` (klucz + etykieta „Drugie imię").
- `zaproponuj_mapowanie` mapuje znormalizowane nagłówki „drugie imię"
  (`drugie_imię`), „Drugie Imie" (`drugie_imie`), „drugie_imiona" →
  `drugie_imię`.
- `waliduj_mapowanie` **nie** wymaga `drugie_imię` (mapowanie
  nazwisko+imię+jednostka nadal poprawne) oraz zgłasza duplikat, gdy dwa
  nagłówki mapują na `drugie_imię`.

### `src/import_pracownikow/tests/test_parsers/test_wartosci.py`
Testy jednostkowe `sklej_drugie_imie` (bez DB) — wszystkie 4 przypadki
z tabeli semantyki + potwierdzenie, że klucz `drugie_imię` jest po scaleniu
usunięty z dict.

### Testy analizy (integracyjne, `@pytest.mark.django_db`)
Dobrać najbliższy istniejący wzorzec testu analizy w
`src/import_pracownikow/tests/` (np. `test_analyze*` / `test_views_faza*`),
żeby nie duplikować rusztowania fixture'ów.

- **Scalenie w wierszu**: wiersz z `imię`+`drugie_imię` (po remapie) → po
  `_przetworz_wiersz` utworzony `ImportPracownikowRow` ma
  `dane_znormalizowane["imię"] == "Jan Paweł"` i **brak** klucza
  `drugie_imię`.
- **Matching po scaleniu (dedup zachowany)**: istnieje `Autor(imiona="Jan",
  nazwisko="Kowalski")`; wiersz `imię="Jan"`+`drugie_imię="Paweł"`+
  `nazwisko="Kowalski"` → wiersz dostaje `autor` = ten istniejący i
  `confidence` twardy (strategia „pierwsze imię", 0.95 ≥ próg auto). Pinuje
  kluczową własność „merge nie zrywa deduplikacji".
- **Kolejność vs `osoba_sklejona` (regresja Błędu z reviewu)**: wiersz z
  `osoba_sklejona="dr Jan Kowalski"` + `drugie_imię="Paweł"` **bez** kolumny
  `imię` → `dane_znormalizowane["imię"] == "Jan Paweł"` (a nie „Paweł").
  Test przypina wymóg „scalać PO rozbiciu".

## Changelog

Fragment towncrier (typ: `feature`) w `src/bpp/newsfragments/` — skill
`towncrier-fragment`.

## Ryzyka / uwagi

- **Matching po scaleniu**: `imiona = "Jan Paweł"` dopasuje istniejącego
  „Jan …" po strategii „pierwsze imię" (0.95), ale exact-full (1.00) trafi
  tylko w autora zapisanego dokładnie jako „Jan Paweł". To zgodne z intencją:
  gdy plik dostarcza dwa imiona, pełny string imion jest wartością docelową.
- **Idempotencja re-analizy**: scalanie działa na `dane_form` budowanym od
  zera z pliku przy każdej analizie (`on_restart` kasuje wiersze), więc nie
  ma ryzyka podwójnego sklejenia.
- **Profile mapowania**: istniejące `ProfilMapowania` nie mają `drugie_imię`
  w JSON — działają bez zmian; nowe profile mogą go zawierać.
- **Znane ograniczenie (świadome)**: gdy plik ma naraz `imię` już zawierające
  drugie imię (np. „Jan Paweł") i osobną kolumnę `drugie_imię="Paweł"`,
  scalenie da „Jan Paweł Paweł". Trzymamy zatwierdzoną, prostą regułę
  konkatenacji spacją (bez deduplikacji tokenów) — sytuacja jest sprzeczna
  wewnętrznie (po co osobne drugie imię, skoro `imię` już je zawiera) i
  rzadka. Gdyby okazała się realna, guard „nie doklejaj tokenu już obecnego
  w `imię`" jest trywialny do dodania.
- **Artefakty zewnętrzne bez zmian**: statyczny plik wzorcowy
  `src/import_pracownikow/tests/` / dokumentacja administratora
  (`docs/administrator/import-pracownikow.md`) opisują istniejące kolumny —
  „Drugie imię" jest opcjonalną kolumną dodatkową, więc nie wymagają
  aktualizacji (można wspomnieć o niej w docs przy okazji, poza zakresem).
