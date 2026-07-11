# Import patentów z SQLite (ppm_harvester) — projekt techniczny

Data: 2026-07-11
Gałąź: `feat-import-sqlite`
Worktree: `~/Programowanie/bpp-import-sqlite`

## 1. Cel i kontekst

`ppm_harvester` (osobne repo, `~/Programowanie/ppm_harvester`) zbiera rekordy
z portalu PPM UMLub (Omega-PSIR) do pliku `ppm.sqlite3`. Interesujące dane
siedzą w tabeli `records`:

| kolumna       | typ  | uwaga                                              |
|---------------|------|----------------------------------------------------|
| `type`        | TEXT | rodzaj rekordu (obecnie w bazie **tylko** `patent`)|
| `source_id`   | TEXT | stabilny identyfikator PPM (np. `UML0092643b...`)  |
| `source_url`  | TEXT | URL strony szczegółów                              |
| `parsed_json` | TEXT | wyekstrahowane pola jako JSON                       |
| `raw_html`, `content_hash`, `fetched_at`, `parsed_at` | | nieużywane przez import |

Klucz główny to `(type, source_id)`.

Cel: **jednorazowo-powtarzalny import 330 patentów** z tego pliku do modeli
BPP `Patent` / `Patent_Autor`, z **dopasowaniem autorów** do istniejących
rekordów `Autor` (reużywając fuzzy-matcher BPP) i z **ręcznym uzgadnianiem**
przypadków niepewnych przez człowieka, zanim cokolwiek powstanie w bazie.

### Kształt `parsed_json` dla patentu

Pola górnego poziomu (obecne w **każdym** z 330 rekordów):
`source_id`, `source_url`, `title`, `inventors` (lista stringów
`"Imię Nazwisko"`, śr. 4.4/rekord, max 12), `application_number`,
`application_date`, `ipc` (lista MKP), `patent_score`, `owner_unit`,
`all_fields` (słownik z polskimi kluczami).

Istotne klucze w `all_fields` (częstość / 330):
- `Numer patentu/prawa` (330, np. `Pat.247645`)
- `Data udzielenia prawa` (330, np. `19-05-2025`)
- `Numer zgłoszenia (w pierwszym kraju zgłoszenia powyżej)` (262)
- `Data zgłoszenia (w pierwszym kraju zgłoszenia powyżej)` (265)
- `Nazwa wynalazku / wzoru / utworu w języku angielskim` (262)
- `Opis w języku polskim` (255), `Opis w języku angielskim` (5)
- `Klasyfikacja MKP` (258)
- `Jednostka zgłaszająca (właściciela) patentu z UML` (312)
- rok-znaczone punktacje: `Punktacja patentu (2025)` itd.

> Fakty pomierzone na `ppm.sqlite3` (330 rekordów, weryfikacja recenzji):
> - `Numer patentu/prawa` (`all_fields`): **330/330 obecne i unikalne** →
>   klucz idempotencji (patrz §7).
> - `source_url`: **330/330 obecne i unikalne**.
> - `application_number`: **68 pustych**, 262 obecne i unikalne.
> - `application_date`: **65 pustych**.
> - `Data udzielenia prawa`: 330/330 obecne (fallback dla `rok`).
> Import musi tolerować puste `application_number`/`application_date`.

## 2. Decyzje projektowe (zatwierdzone z użytkownikiem)

1. **Kształt narzędzia:** aplikacja Django **w repo** `src/import_sqlite/`
   (nie osobne repo, nie ekstrakcja `bpp-core`). Sterowanie przez
   **management commands** + edytowalne pliki **CSV** do przeglądu. Bez UI
   webowego. Bez własnych modeli DB — stan przeglądu żyje w plikach CSV.
2. **Warstwa czytająca SQLite jest generyczna** (po kolumnie `type`), a
   konkretny **handler `patent`** jest pierwszym i na razie jedynym
   zaimplementowanym typem. Struktura zostawia miejsce na kolejne typy, ale
   ich **nie** implementujemy (YAGNI — w bazie jest tylko `patent`).
3. **Autorzy niedopasowani (status `BRAK`)**: nic nie powstaje po cichu.
   Nowego `Autor`a tworzymy **wyłącznie na jawne polecenie** — użytkownik
   wpisuje `NOWY` w kolumnie `decyzja`.
4. **Klucz re-run (idempotencja):** `numer_prawa_wylacznego` (ze źródłowego
   `Numer patentu/prawa`, np. `Pat.247645`). **Zmiana wobec pierwotnego
   wyboru użytkownika (`numer_zgloszenia`)** wymuszona weryfikacją: numer
   zgłoszenia brakuje w 68/330 rekordach, a `informacja_z` to FK do słownika
   (nie da się tam trzymać `PPM:<source_id>`). `Numer patentu/prawa` jest
   330/330 obecny i unikalny — twardo lepszy. `source_url` (`www`, 330/330
   unikalny) trzymamy jako drugorzędny nośnik proweniencji.
5. **Rok patentu (`Patent.rok`):** rok z `application_date`; gdy brak (65
   rekordów) → **fallback: rok z `Data udzielenia prawa`** (330/330). Pole
   `rok` jest NOT NULL bez defaultu — nigdy nie może zostać puste.
6. **`Patent.wydzial`:** `aktualna_jednostka` **pierwszego dopasowanego
   twórcy, którego jednostka ma `skupia_pracownikow=True`** (czyli realny
   pracownik uczelni; nie „Obca jednostka", nie „Wydział"). Nie fuzzy-matching
   tekstu „owner_unit".
7. **Punktacja:** zostawiamy własny mechanizm liczenia punktów BPP
   (dyscypliny). `patent_score` **nie** jest wciskany w pole punktowe.
8. **Metadane bogate** (tytuł ang., abstrakt, MKP/IPC, patent_score) trafiają
   do `szczegoly` / `adnotacje`, bez wymyślania nowych pól modelu.

## 3. Architektura aplikacji `import_sqlite`

```
src/import_sqlite/
    __init__.py
    apps.py                      # AppConfig; rejestracja w INSTALLED_APPS
    reader.py                    # generyczny czytnik tabeli `records` (sqlite3 stdlib)
    review_io.py                 # zapis/odczyt CSV-ów przeglądu (autorzy, patenty)
    core/
        __init__.py
        author_names.py          # split "Imię Nazwisko" -> {given, family}; kanonizacja
        author_matching.py       # wiring do crossref_bpp.Komparator + agregacja distinct
    handlers/
        __init__.py
        base.py                  # interfejs handlera typu rekordu (kontrakt)
        patent.py                # PatentData dataclass + parsed_json -> PatentData + zapis do BPP
    management/commands/
        import_sqlite_scan.py    # faza 1: scan -> CSV-y
        import_sqlite_apply.py   # faza 2: apply -> tworzy/aktualizuje rekordy
    tests/
        conftest.py
        test_author_names.py
        test_reader.py
        test_scan.py
        test_apply.py
```

**Zasada separacji:** logika czysta (parsowanie JSON→dataclass, split nazwisk,
IO CSV, agregacja distinct-nazwisk) jest **odseparowana od ORM** i testowalna
bez bazy. Dotknięcia bazy (Komparator, tworzenie `Autor`/`Patent`) są w
`author_matching.py` i `handlers/patent.py`, testowane z `@pytest.mark.django_db`
+ `model_bakery`.

Reużywane z BPP (import wprost — apka jest w tym samym projekcie Django):
- `crossref_bpp.core.Komparator.porownaj_author({family, given, orcid})`
  → status (`DOKLADNE`/`LUZNE`/`WYMAGA_INGERENCJI`/`BRAK`), `sugerowany`,
  `kandydaci` (każdy: `.autor`, `.pewnosc`, `.powod`, `.publikacji`).
- `import_common.core.autor.znajdz_kandydatow_autora` (pod spodem Komparatora;
  strategie iexact + `unaccent` — **wymaga żywej bazy BPP z rozszerzeniem
  `unaccent`** i wypełnionej tabeli `Autor`; matcher NIE jest czystą funkcją).
- `bpp.models.Patent`, `Patent_Autor`, `Autor`, `Uczelnia`.
- `record.dodaj_autora(autor, jednostka, zapisany_jako=..., kolejnosc=...,
  afiliuje=...)`.
- `Autor.objects.create(imiona=, nazwisko=)` + `autor.dodaj_jednostke(obca)`
  dla `NOWY` (wzór z `importer_publikacji.views.authors._create_single_author`).
- `Uczelnia.obca_jednostka` jako jednostka dla obcych/nowych twórców.

## 4. Przepływ dwufazowy

```bash
# Faza 1 — SCAN: czyta sqlite, auto-matchuje, wypisuje CSV-y do przeglądu
uv run python src/manage.py import_sqlite_scan \
    ~/Programowanie/ppm_harvester/ppm.sqlite3 \
    --typ patent \
    --out-autorzy autorzy_do_uzgodnienia.csv \
    --out-patenty patenty_do_przegladu.csv

#  ← użytkownik edytuje autorzy_do_uzgodnienia.csv (wypełnia kolumnę `decyzja`)

# Faza 2 — APPLY: wczytuje decyzje, tworzy/aktualizuje Patenty
uv run python src/manage.py import_sqlite_apply \
    ~/Programowanie/ppm_harvester/ppm.sqlite3 \
    --typ patent \
    --autorzy autorzy_do_uzgodnienia.csv \
    [--dry-run]
```

- `--dry-run`: całość w transakcji z `transaction.set_rollback(True)` na końcu;
  raportuje, co **by** powstało/się zmieniło, nic nie utrwala.
- `apply` nadpisuje `patenty_do_przegladu.csv` finalnym statusem każdego
  patentu (UTWORZONY / ZAKTUALIZOWANY / WSTRZYMANY + powód).
- Oba polecenia są **idempotentne** i **wznawialne**: po uzupełnieniu braków
  w CSV kolejny `apply` doimportowuje resztę, istniejące aktualizuje.

## 5. Dopasowanie i kanonizacja autorów (rdzeń)

### 5.1 Split nazwiska
`inventors` to stringi `"Imię Nazwisko"` (kolejność: imię-najpierw, np.
`"Anna Wawruszak"`, `"Andrzej Stepulak"`). Heurystyka:
`given = pierwszy token`, `family = reszta` (obsługuje nazwiska
dwuczłonowe/łącznikowe, np. `"Wirginia Kukuła-Koch"` → given=`Wirginia`,
family=`Kukuła-Koch`). Oryginalny string zachowujemy jako `zapisany_jako`.

### 5.2 Agregacja distinct
Zamiast matchować per-wystąpienie (≈1450 razy), zbieramy **zbiór distinct
stringów nazwisk** ze wszystkich rekordów wybranego typu (≈kilkaset). Dla
każdego distinct wołamy Komparatora **raz**. Wynik → jeden wiersz w
`autorzy_do_uzgodnienia.csv`. Jedna decyzja użytkownika rozprowadza się na
**wszystkie** patenty zawierające ten string.

### 5.3 CSV autorów — `autorzy_do_uzgodnienia.csv`

Kolumny:

| kolumna              | znaczenie                                                        |
|----------------------|------------------------------------------------------------------|
| `nazwisko_zrodlowe`  | oryginalny string z `inventors` (klucz wiersza)                  |
| `given`, `family`    | wynik splitu (do wglądu)                                         |
| `wystapien`          | w ilu patentach ten string występuje                            |
| `status`             | znormalizowany label (patrz niżej)                              |
| `kandydat_1..3`      | top-3 kandydaci: `Nazwisko Imię (#pk, pewność, N publ.)`         |
| `decyzja`            | **wypełnia człowiek** (patrz semantyka niżej)                    |

> **Mapowanie statusu Komparatora → label CSV.** `porownaj_author` przy braku
> dopasowania zwraca `BRAK_DOPASOWANIA` ze statusem **`BLAD`** (a nie `BRAK`;
> `crossref_bpp/core.py:101`), a `kandydaci` bywa `None`. W CSV normalizujemy:
> `DOKLADNE`→`DOKLADNE`, `LUZNE`→`LUZNE`, `WYMAGA_INGERENCJI`→`WYMAGA_INGERENCJI`,
> `BLAD`/`BRAK`/brak kandydatów → **`BRAK`**. Handler musi tolerować
> `kandydaci=None`.

Semantyka `decyzja`:
- **pk `Autor`a** (liczba, np. `441`) → mapuj ten string na tego autora.
- **`NOWY`** → utwórz nowego `Autor`a (`imiona=given`, `nazwisko=family`,
  przypisany do `obca_jednostka`).
- **puste** → string **nierozstrzygnięty**. Wiersze `DOKLADNE` są **prefillowane**
  pk-iem sugerowanego autora (można nadpisać). Pozostałe statusy startują puste.

**Sortowanie po znormalizowanym nazwisku** — inconsistentne pisownie tego
samego człowieka (`Kowalski Jan` vs `Kovalski Jan`) lądują **obok siebie**;
użytkownik widzi rozjazd i kieruje obie `decyzja` na ten sam pk → dwie pisownie
zlewają się w jednego `Autor`a. To realizuje wymóg „spójnego zmatchowania
konsekwentnej literówki w wielu rekordach".

### 5.4 Reguły jednostki / afiliacji przy `dodaj_autora`
> Uwaga krytyczna (weryfikacja): `dodaj_autora` przekazuje `afiliuje` **wprost**
> do modelu i woła `full_clean()` (`models/util.py:76-78`). `_waliduj_afiliacje`
> (`abstract/authors.py:231`) rzuca `ValidationError`, gdy `afiliuje=True` na
> jednostce z `skupia_pracownikow=False` — **a `obca_jednostka` też ma FK do
> uczelni**, więc reguła „należy do uczelni" była błędna. Właściwe kryterium to
> `skupia_pracownikow`.

- **dopasowany `Autor`:** `jednostka = autor.aktualna_jednostka`
  (fallback `obca_jednostka`, jeśli `aktualna_jednostka` puste);
  `afiliuje = bool(jednostka.skupia_pracownikow)`.
- **`NOWY`:** `jednostka = obca_jednostka`; `afiliuje = False`.
- `Patent.wydzial` = `aktualna_jednostka` **pierwszego** (wg kolejności w
  `inventors`) dopasowanego twórcy, którego `aktualna_jednostka` ma
  `skupia_pracownikow=True`; jeśli takiego brak → `wydzial = None`.
- **Edge-case „Wydział":** jeśli czyjaś `aktualna_jednostka` ma rodzaj z
  `autor_moze_afiliowac=False` (`authors.py:243`), `dodaj_autora` z
  `afiliuje=True` padnie mimo `skupia_pracownikow=True`. Handler łapie
  `ValidationError` per patent i **wstrzymuje** rekord (§6), nie wywala całego
  `apply`.

### 5.5 Dedupe twórców w obrębie patentu
Po rozwiązaniu decyzji dwa różne stringi (`Kowalski Jan`, `Kovalski Jan`) mogą
wskazać **ten sam** pk `Autor`a w jednym patencie → `unique_together
(rekord, autor, typ_odpowiedzialnosci)` rzuci `ValidationError`. Dlatego
**deduplikujemy listę twórców per patent po rozwiązanym pk** (pierwsze
wystąpienie wygrywa `zapisany_jako` i `kolejnosc`) przed wołaniem `dodaj_autora`.

## 6. Obsługa rekordów niepewnych (wstrzymanie)

Patent dostaje status **`WSTRZYMANY`** (pomijany, zaimportuje się przy kolejnym
`apply` po naprawie) w każdym z przypadków:
- którykolwiek twórca ma `decyzja` puste (z nazwą blokującego twórcy);
- `ValidationError` przy `dodaj_autora` (np. edge-case „Wydział", §5.4) —
  łapiemy per patent, nie wywalamy całego `apply`;
- niejednoznaczny klucz idempotencji (`>1` istniejący `Patent` o tym
  `numer_prawa_wylacznego`) — nie zgadujemy (§7).

Re-run jest bezpieczny i przyrostowy. Cały `apply` biegnie w **jednej
transakcji**; wstrzymanie pojedynczego patentu = `savepoint` rollback tylko dla
niego (nie całości), reszta tworzy się normalnie.

## 7. Mapowanie pól `Patent`

| Pole BPP                | Źródło                                                         |
|-------------------------|----------------------------------------------------------------|
| `tytul_oryginalny`      | `title`, przepuszczony przez `safe_html` (Patent.clean nie leci przy save) |
| `rok`                   | rok z `application_date`; fallback rok z `Data udzielenia prawa` (NOT NULL) |
| `numer_zgloszenia`      | `application_number` (`P.445383`), może być puste             |
| `data_zgloszenia`       | `application_date` (parsuj `DD-MM-YYYY`), null jeśli brak      |
| `numer_prawa_wylacznego`| `all_fields["Numer patentu/prawa"]` (`Pat.247645`) — **klucz re-run** |
| `data_decyzji`          | `all_fields["Data udzielenia prawa"]`, null jeśli brak        |
| `status_korekty`        | **wymagane FK (bez defaultu!)** → `Status_Korekty` „przed korektą" (fallback `.first()`) |
| `wydzial`               | patrz §5.4                                                     |
| `www`                   | `source_url` (nośnik proweniencji, 330/330 unikalny)          |
| `informacja_z`          | FK → `get_or_create` jednego wpisu `Zrodlo_Informacji` „PPM (ppm.umlub.pl)" (audyt; **nie** klucz) |
| `charakter_formalny`    | auto (`PAT`) — `cached_property` modelu                       |
| `jezyk`                 | auto (polski) — `cached_property` modelu                      |
| `szczegoly`             | **CharField(512)!** tytuł ang. + MKP/IPC + patent_score, przycięte do 512; nadmiar → `adnotacje` |
| `adnotacje`             | TextField: abstrakt PL/EN, nadmiar ze `szczegoly`             |
| twórcy → `Patent_Autor` | `dodaj_autora(...)` w kolejności `inventors` (po dedupe §5.5); `zapisany_jako` = oryginalny string |

Parsowanie dat: format źródłowy `DD-MM-YYYY`. Braki/nieparsowalne → `None`
(pola nullable), nigdy wyjątek wywalający cały import — **poza `rok`**, który ma
gwarantowany fallback (data udzielenia).

### Idempotencja (klucz re-run)
Klucz = `numer_prawa_wylacznego` (330/330 obecny i unikalny w źródle):
`Patent.objects.filter(numer_prawa_wylacznego=...)`.

- **0** → **create**.
- **1** → **update**: aktualizuj pola skalarne (nadpisujemy danymi z PPM —
  import jest źródłem prawdy dla tych patentów); twórców synchronizuj przez
  `delete()` dotychczasowych `Patent_Autor` + odtworzenie z decyzji
  (deterministyczne). Uwaga: `numer_prawa_wylacznego` nie jest `unique` w DB,
  więc update MOŻE trafić ręcznie wprowadzony patent — w CSV oznaczamy taki
  wiersz `ZAKTUALIZOWANY`, żeby bibliotekarz widział nadpisanie.
- **>1** → `WSTRZYMANY` „niejednoznaczny klucz" (nie zgadujemy).

Na końcu `apply` (po utworzeniu/aktualizacji wszystkiego) wołamy
`denorms.flush()` — inaczej `opis_bibliograficzny_cache`/`slug` zostają puste do
najbliższego flusha (wzorzec: `bpp/management/commands/zamapuj_wydawcow.py`).

## 8. Testy (TDD)

`model_bakery` na istniejących `Autor`/`Jednostka`/`Uczelnia`; mały fixture
sqlite w tmp z ręcznie zbudowanymi blobami `parsed_json` pokrywającymi:

1. dopasowanie `DOKLADNE` (prefill pk),
2. dopasowanie `LUZNE` (kandydat, ale nie prefill),
3. `BRAK` → `NOWY` (tworzenie `Autor` + `obca_jednostka`, `afiliuje=False`),
4. brak `application_number` **i** `application_date` → patent i tak powstaje;
   `rok` z daty udzielenia; klucz re-run z `numer_prawa_wylacznego`,
5. nazwisko łącznikowe (`Kukuła-Koch`) — poprawny split,
6. dwie pisownie tego samego (`Kowalski`/`Kovalski`) mapowane na ten sam pk —
   twórca **zdeduplikowany** w patencie (bez `ValidationError`, §5.5),
7. patent z nierozstrzygniętym twórcą → `WSTRZYMANY`, brak utworzenia,
8. idempotencja: drugi `apply` po `numer_prawa_wylacznego` nie duplikuje, aktualizuje,
9. `--dry-run` nic nie utrwala,
10. `afiliuje` = `skupia_pracownikow` jednostki (dopasowany do jednostki
    zbierającej pracowników → `True`; `NOWY`/obca → `False`),
11. `wydzial` = `aktualna_jednostka` 1. twórcy z `skupia_pracownikow=True`,
12. `status_korekty` ustawione (create nie pada na IntegrityError),
13. `decyzja` = pk nieistniejącego `Autor`a → błąd przy wczytaniu CSV
    (walidacja **przed** transakcją), nie w środku.

Testy czyste (`test_author_names`, IO CSV, agregacja distinct, normalizacja
statusu `BLAD`→`BRAK`) bez bazy; testy `scan`/`apply` z `@pytest.mark.django_db`.
**Fixtures muszą tworzyć wpis `Typ_Odpowiedzialnosci(skrot="aut.")`** (używany
przez `dodaj_autora`) oraz `Status_Korekty`, `Charakter_Formalny(skrot="PAT")`,
`Jezyk` polski, `Uczelnia` z `obca_jednostka` — inaczej handler padnie na
`DoesNotExist`.

## 9. Rejestracja i uruchamianie

- Dodać `import_sqlite` do `INSTALLED_APPS` w `src/django_bpp/settings/base.py`.
- Bez migracji (apka nie ma modeli) — ale dopisać do `packages.find.include`
  w `pyproject.toml` (spójność z resztą listy).
- Uczelnia/jednostka obca: na starcie `scan`/`apply` pobrać
  `Uczelnia.objects.get_single_uczelnia_or_fail()` i **sprawdzić
  `uczelnia.obca_jednostka is not None`** — jeśli brak, głośno paść z instrukcją
  (nie wpadać w `IntegrityError` w środku pętli; `jednostka` w `Patent_Autor`
  jest NOT NULL).
- Uruchamianie: przeciw żywej bazie BPP (Komparator = iexact + `unaccent`,
  wymaga Postgresa z rozszerzeniem `unaccent` i wypełnionej tabeli `Autor`).
  Lokalnie: `run-site` / dump; dla realnego importu — baza docelowa.

## 10. Poza zakresem (YAGNI)

- Handlery dla typów innych niż `patent` (w bazie ich nie ma).
- UI webowe / rozszerzanie `importer_publikacji`.
- Fuzzy-matching tekstu „owner_unit" do `Jednostka` (zastąpione regułą §5.4).
- Wpychanie `patent_score` w pola punktowe (liczy BPP wg dyscyplin).
- Ekstrakcja `bpp-core` / instalowalny pakiet (sprzężenie runtime i tak by
  zostało; ogromny refactor bez zysku dla tego zadania).
