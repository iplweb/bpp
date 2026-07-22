# Import pracowników — rozpoznawanie kolumn wykazu (Data od/do, Gł. zakład pracy, podwójny wymiar etatu)

**Data:** 2026-07-13
**Moduł:** `src/import_pracownikow/` + `src/import_common/`
**Bazuje na:** `dev` @ `3c720587c` (po scaleniu #576 „synchronizacja dat
zatrudnienia" i #577 „xss tytuł/opis").
**Powiązany spec (osobny, już zaimplementowany):**
`2026-07-13-import-pracownikow-synchronizacja-dat-zatrudnienia-design.md` (#576).

---

## 1. Kontekst i cel

Prawdziwy plik `wykaz 2026.xlsx` (arkusz „30.06.2026", 15 kolumn) importuje się
źle, bo **warstwa rozpoznawania kolumn** nie zna nagłówków, których ten plik
faktycznie używa. Zweryfikowany stan na `dev` (`normalize_cell_header` →
`_SYNONIMY` w `mapping.py`):

| Kolumna w pliku | Znormalizowany nagłówek | Obecnie rozpoznane? | Cel |
|---|---|---|---|
| `Data od` | `data_od` | ❌ → `POLE_POMIN` | `data_zatrudnienia` (`rozpoczal_prace`) |
| `Data do` | `data_do` | ❌ → `POLE_POMIN` | `data_końca_zatrudnienia` (`zakonczyl_prace`) |
| `Gł. zakład pracy` (wart. `T`/`N`) | `gł_zakład_pracy` | ❌ → `POLE_POMIN` | `podstawowe_miejsce_pracy` (bool) |
| `Wymiar etatu` (tekst, np. `1/2 etatu`) | `wymiar_etatu` | ⚠️ → verbatim do słownika | `wymiar_etatu` (kanoniczny ułamek) |
| `Wymiar etatu` (ułamek, np. `0,5`) | `wymiar_etatu_2` | ❌ → `POLE_POMIN` (cicho gubione) | `wymiar_etatu` (kanoniczny ułamek) |

**Ważne rozróżnienie względem #576.** #576 dał *logikę synchronizacji dat*
(`okresy.py` resolver, nowy okres, widoczność `POLA_ROZNIC` z etykietami
„Data od"/„Data do"). To są **wewnętrzne** klucze porównywarki, NIE synonimy
nagłówków pliku. Auto-rozpoznanie literalnych nagłówków `Data od`/`Data do`
**nadal nie istnieje** — operator musi je dziś mapować ręcznie. Ten spec domyka
tę lukę i NIE dotyka logiki sync (semantyka `rozpoczal`/`zakonczyl` bez zmian).

**Cel:** żeby `wykaz 2026.xlsx` (i pliki o tym układzie nagłówków) mapował się
**automatycznie**, z poprawnym parsowaniem `T`/`N`, dat ISO oraz z **kanonicznym**
wymiarem etatu walidowanym krzyżowo między dwiema kolumnami.

Trzy niezależne części: **(A)** nagłówki dat, **(B)** główny zakład pracy,
**(C)** podwójny wymiar etatu.

---

## 2. Część A — nagłówki `Data od` / `Data do`

### 2.1 `mapping.py` — `_SYNONIMY`

Dopisać (obok istniejących `data_zatrudnienia`/`data_końca_zatrudnienia`):

```python
"data_od": "data_zatrudnienia",
"data_do": "data_końca_zatrudnienia",
```

To wystarczy — reszta ścieżki (value-parsing, integracja, sync z #576) już
konsumuje klucze `data_zatrudnienia`/`data_końca_zatrudnienia`. Dodanie
synonimów wzmacnia też auto-detekcję wiersza-nagłówka (`TRY_NAMES =
sorted(set(_SYNONIMY.keys()))`, `MIN_POINTS = 2`).

### 2.2 Parsowanie wartości — daty ISO

Plik niesie daty w **ISO** (`2021-10-01`, `2026-09-30`) oraz pusty `Data do`
(`''`). `parsers/wartosci.py::normalize_date_pl` parsuje tylko `DD.MM.YYYY` →
zwraca `None` dla ISO; ISO/`datetime` łapie dopiero `ExcelDateField` na
`AutorForm`. **Wymaganie:** obie formy (`YYYY-MM-DD` i `DD.MM.YYYY`) oraz pusty
łańcuch muszą przejść do `date`/`None` bez błędu. Rozszerzyć `normalize_date_pl`
(albo `normalizuj_wartosci_wiersza`), by próbowało `YYYY-MM-DD`, gdy
`DD.MM.YYYY` nie pasuje; pusty → `None`. Nie psuć istniejącej ścieżki
`ExcelDateField`.

> Uwaga: `Data od`/`Data do` to generyczne stringi, ale w `_SYNONIMY` importu
> pracowników nie kolidują z niczym (słownik jest modułowy).

---

## 3. Część B — `Gł. zakład pracy` → `podstawowe_miejsce_pracy`

### 3.1 `mapping.py` — `_SYNONIMY`

Dopisać (wszystkie warianty; `normalize_cell_header` NIE usuwa polskich znaków,
więc listujemy diakrytyczne i ASCII):

```python
"gł_zakład_pracy": "podstawowe_miejsce_pracy",
"gl_zaklad_pracy": "podstawowe_miejsce_pracy",
"główny_zakład_pracy": "podstawowe_miejsce_pracy",
"glowny_zaklad_pracy": "podstawowe_miejsce_pracy",
```

Nie ruszać istniejących `"zaklad"/"zakład" → "nazwa_jednostki"` (to inna kolumna
— „Nazwa jednostki"). Nowe klucze są pełnymi frazami, więc nie kolidują.

### 3.2 Wartość `T` / `N`

Bez zmian w parserze: `normalize_boolean` już mapuje `"t"→True`, `"n"→False`
(oraz `tak/prawda/true/p` / `nie/fałsz/false/f`). Integracja
(`_integrate_autor_jednostka`, `podstawowe_miejsce_pracy`) już rozróżnia
`False` (jawnie „nie podstawowe") od `None`/braku (domyślnie TAK) i pilnuje
pojedynczego podstawowego miejsca pracy przez `ustaw_podstawowe_miejsce_pracy()`
+ DEFERRED constraint (mig. 0444). Semantyka bez zmian — po prostu kolumna
zaczyna być czytana.

---

## 4. Część C — podwójny „Wymiar etatu" → kanoniczny ułamek

### 4.1 Problem

`rename_duplicate_columns` (już działa) rozdziela dwa identyczne nagłówki
`Wymiar etatu` na klucze `wymiar_etatu` (1. kolumna = tekst) i `wymiar_etatu_2`
(2. kolumna = ułamek). Dziś: `wymiar_etatu` (`1/2 etatu`) idzie **verbatim** do
słownika `Wymiar_Etatu` (tworzy śmieciowy wpis), a `wymiar_etatu_2` (`0,5`)
wpada w `POLE_POMIN` i jest **cicho gubione**.

Słownik `Wymiar_Etatu` (FK z `Autor_Jednostka.wymiar_etatu`) jest już
zaśmiecony dziesiątkami form tej samej wartości: `1`/`1.0`, `0,5`/`0.5`,
`0,666666667`/`0.666666667`/`0,666666666666`, `pełny etat`, `brak`, `0.88`, …
Istnieją też jednak „dobre" formy: `1`(id1), `0,5`(id2), `0,25`(id3),
`0,75`(id5), `0,67`(id4) — polski przecinek, minimalne cyfry.

### 4.2 Decyzja (z brainstormingu)

- **Dwa etykietowane pola docelowe** w mapowaniu: `wymiar_etatu_tekst`
  („Wymiar etatu (tekst)") i `wymiar_etatu_ulamek` („Wymiar etatu (ułamek)").
  Operator widzi je rozdzielnie i może poprawić.
- **Jeden tolerancyjny parser** dla OBU (odporność na zamienioną kolejność
  kolumn).
- **Walidacja krzyżowa** obu wartości; rozbieżność → **błąd wiersza**.
- **Zapis kanoniczny**: ułamek dziesiętny, polski przecinek, minimalne cyfry.
- **Kolumna dziesiętna autorytatywna** dla zapisu; tekst służy do walidacji.
- **Poza zakresem**: czyszczenie istniejących duplikatów w słowniku.

### 4.3 `mapping.py` — synonimy i pola docelowe

```python
# POLA_DOCELOWE — zamiast pojedynczego ("wymiar_etatu", "Wymiar etatu"):
("wymiar_etatu_tekst",  "Wymiar etatu (tekst)"),
("wymiar_etatu_ulamek", "Wymiar etatu (ułamek)"),

# _SYNONIMY:
"wymiar_etatu":   "wymiar_etatu_tekst",     # 1. kolumna (i legacy single-col)
"wymiar_etatu_2": "wymiar_etatu_ulamek",    # 2. kolumna
"etat":           "wymiar_etatu_tekst",
"wymiar":         "wymiar_etatu_tekst",
```

Zgodność wstecz profili mapowania (`ProfilMapowania`): moduł jest jeszcze
**niewydany** (cała praca na `dev`), więc ryzyko starych profili z kluczem
`wymiar_etatu` jest minimalne; jeśli trzeba — przyjmować `wymiar_etatu` jako
alias `wymiar_etatu_tekst` przy wczytaniu profilu. Udokumentować w planie.

### 4.4 Parser `parsuj_wymiar_etatu(s) -> Fraction | None`

Lokalizacja: `src/import_common/normalization.py` (obok `normalize_wymiar_etatu`)
lub nowy helper w `import_pracownikow/parsers/`. Reguły:

- `None` / pusty / same białe znaki → `None`;
- lower + trim; usuń sufiks `etatu`/`etat`;
- `pełny`/`pełen`/`cały`/`caly` (± „etat") → `Fraction(1)`;
- `N/M` (np. `1/2`, `3/4`, `1/4`) → `Fraction(N, M)`;
- dziesiętne `0,5` / `0.5` / `1` / `,5` → `Fraction` z `Decimal` (przecinek→kropka);
- inaczej → **błąd parsowania** (nieznana forma).

### 4.5 Kanonizacja `kanoniczny_wymiar(frac) -> str`

- mianownik 1 → `str(licznik)` (np. `"1"`);
- inaczej → dziesiętny z **polskim przecinkiem**, max 2 miejsca, obetnij zera
  końcowe: `0.5→"0,5"`, `0.75→"0,75"`, `0.25→"0,25"`, `2/3→"0,67"`.

Kanoniczna forma **matchuje istniejące dobre wpisy** słownika przez
`matchuj_wymiar_etatu` (`nazwa__iexact`): `"0,5"`=id2, `"1"`=id1, `"0,25"`=id3,
`"0,75"`=id5, `"0,67"`=id4 → **przestajemy dokładać śmieci** typu `1/2 etatu`.

### 4.6 Walidacja krzyżowa i scalenie

Nowy krok normalizacji wiersza (w `parsers/wartosci.py` /
`_przetworz_wiersz` w `analyze.py`), produkujący pojedynczy `wymiar_etatu`
(string kanoniczny) w `dane_form`, żeby **downstream** (`_matchuj_slownik_lub_odroc`,
integracja, `_integrate_autor_jednostka`) pozostał **bez zmian**:

```
t = parsuj_tolerancyjnie(dane_form.pop("wymiar_etatu_tekst", None))  # None gdy nieparsowalne
u = parsuj_tolerancyjnie(dane_form.pop("wymiar_etatu_ulamek", None))
jeśli t i u oba są ułamkami i round(t,2) != round(u,2):
    -> XLSMatchError (BŁĄD WIERSZA, pokaż obie wartości)   # JEDYNY twardy błąd
kan = u jeśli u else t                                     # dziesiętna autorytatywna
jeśli kan (ułamek):  dane_form["wymiar_etatu"] = kanoniczny_wymiar(kan)
inaczej:             dane_form["wymiar_etatu"] = surowa (ułamek_raw|tekst_raw)  # pass-through
```

- **Twardy błąd TYLKO** gdy OBIE kolumny to sparsowalne ułamki, które się
  RÓŻNIĄ (`round(t,2) != round(u,2)`) → `XLSMatchError` (analiza fail-fast,
  „nie przyjmujemy takiego excela"). Komunikat wskazuje wiersz i obie wartości.
- **Nieparsowalna wartość NIE jest błędem** — nieliczbowy wpis (np. `brak`,
  legalna wartość słownika) przechodzi **surowo** do `wymiar_etatu` (stara,
  tolerancyjna ścieżka słownika). Pojedynczą kolumnę **akceptujemy** — nie
  wywalamy importu na nieparsowalnym wymiarze.
- Sparsowalny ułamek → zawsze kanonizowany (koniec śmieci typu `1/2 etatu`).
- Tolerancja zaokrągleń (`round(...,2)`) obsługuje `2/3` vs `0,67` itp.

---

## 5. Warstwa błędów

Analiza importu jest **fail-fast** (jeden `XLSParseError`/`XLSMatchError`
przerywa cały run z komunikatem wskazującym wiersz). W tej architekturze „błąd
wiersza" = przerwanie runu z jawnym wskazaniem winnego wiersza i wartości.

Twardy `XLSMatchError` wyzwala **wyłącznie** rozbieżność DWÓCH sparsowalnych
kolumn wymiaru (ten sam wymiar zapisany niespójnie — „nie przyjmujemy takiego
excela"). Wartość **nieparsowalna** (np. `brak`) **NIE** jest błędem: przechodzi
surowo do słownika (stara ścieżka). Gdy w pliku jest tylko jedna kolumna wymiaru
— akceptujemy ją bez walidacji krzyżowej (parsowalną kanonizujemy, nieparsowalną
przekazujemy surowo). To spójne z decyzją usera („jedna kolumna → akceptuj ją")
oraz z tolerancyjnym wzorcem walidacji e-maila w tym module.

---

## 6. Plan testów (TDD — najpierw testy)

**Nagłówki (`mapping.py` / `zaproponuj_mapowanie`):**
- `data_od`→`data_zatrudnienia`, `data_do`→`data_końca_zatrudnienia`;
- `gł_zakład_pracy` + `gl_zaklad_pracy` + `główny_zakład_pracy` +
  `glowny_zaklad_pracy` → `podstawowe_miejsce_pracy`;
- dwa `Wymiar etatu` → `wymiar_etatu_tekst` + `wymiar_etatu_ulamek`
  (przez `rename_duplicate_columns`);
- `"zakład"` NADAL → `nazwa_jednostki` (regres-guard).

**Wartości:**
- `normalize_boolean("T")→True`, `("N")→False`;
- daty: `2021-10-01` (ISO), `01.10.2021` (PL), `''`(pusty) → `date`/`None`.

**Parser wymiaru:** `pełny etat`/`1/2 etatu`/`3/4`/`0,5`/`0.5`/`1`/pusty/śmieć
→ `Fraction`/`None`/błąd; `kanoniczny_wymiar` → `"0,5"`/`"1"`/`"0,25"`/`"0,67"`.

**Walidacja krzyżowa:** zgodne (`1/2 etatu` + `0,5`) → `"0,5"`; rozbieżne
(`1/2 etatu` + `1`) → błąd wiersza; jedna kolumna → użyta; brak obu → brak
wymiaru; `2/3 etatu` + `0,67` → zgodne (tolerancja).

**Match słownika:** kanoniczny `"0,5"` matchuje istniejący wpis (NIE tworzy
nowego); `1/2 etatu` NIE trafia już verbatim do słownika.

**E2E:** syntetyczny 2–3 wierszowy XLSX z układem nagłówków wykazu (bez danych
z prawdziwego pliku — RODO): pełna ścieżka analiza→podgląd, sprawdzenie że
`Data od/do`, `Gł. zakład pracy` (T/N), oba wymiary są rozpoznane i wymiar
kanonizowany.

Po implementacji: `uv run pytest src/import_pracownikow/ src/import_common/`
zielone; pełna suita `make tests` (~10 min) — 0 regresji.

---

## 7. Migracje / baseline

**Brak migracji schematu** — zmiany to synonimy mapowania, parser, dane
słownikowe runtime. Baseline odświeżyć **przy scalaniu** (reguła projektu), nie
w tym branchu (kolizja na wielkim pliku między równoległymi branchami importu).

---

## 8. Poza zakresem (świadomie)

- Logika synchronizacji dat (`okresy.py`, nowy okres) — zrobiona w #576.
- Czyszczenie istniejących duplikatów w `Wymiar_Etatu` (osobna migracja danych,
  ryzykowna) — nie ruszamy.
- Odrzucanie całego pliku przy rozbieżności wymiaru — świadomie wybrano
  per-row error.
- Wykrywanie „przeniesień" między jednostkami — osobny mechanizm.

---

## 9. Ryzyka

- **Kolejność kolumn wymiaru** (tekst-vs-ułamek) inna niż w wykazie 2026 →
  mitygacja: jeden tolerancyjny parser dla obu + walidacja na `Fraction`
  (nie na etykiecie).
- **Daty ISO** gubione przez `normalize_date_pl` → mitygacja: jawny fallback
  ISO + test.
- **Profile mapowania** z legacy kluczem `wymiar_etatu` → mitygacja: alias przy
  wczytaniu (moduł niewydany, ryzyko małe).
- **Zaśmiecony słownik** → kanonizacja ogranicza dalszy przyrost; historyczny
  bałagan poza zakresem.
