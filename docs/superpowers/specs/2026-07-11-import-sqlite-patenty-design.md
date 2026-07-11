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

> Uwaga: górnopoziomowe `application_number`/`application_date` są obecne we
> wszystkich 330 rekordach jako klucze, ale mogą być pustymi stringami tam,
> gdzie `all_fields` nie miało odpowiednika (≈65 rekordów bez numeru
> zgłoszenia). Import musi to tolerować (patrz §7 idempotencja).

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
4. **Klucz re-run (idempotencja):** `numer_zgloszenia`; dla ≈65 rekordów bez
   niego fallback na `PPM:<source_id>` zapisany w `informacja_z`.
5. **Rok patentu (`Patent.rok`):** **zawsze rok z daty zgłoszenia**
   (`application_date`).
6. **`Patent.wydzial`:** `aktualna_jednostka` **pierwszego dopasowanego
   twórcy z naszej uczelni** (nie fuzzy-matching tekstu „owner_unit").
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
  trygramy w Postgresie — **wymaga żywej bazy BPP + pg_trgm**).
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
| `status`             | `DOKLADNE`/`LUZNE`/`WYMAGA_INGERENCJI`/`BRAK`                    |
| `kandydat_1..3`      | top-3 kandydaci: `Nazwisko Imię (#pk, pewność, N publ.)`         |
| `decyzja`            | **wypełnia człowiek** (patrz semantyka niżej)                    |

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
- **dopasowany `Autor`:** `jednostka = autor.aktualna_jednostka`
  (fallback `obca_jednostka`, jeśli `aktualna_jednostka` puste);
  `afiliuje = (jednostka należy do naszej Uczelni)`.
- **`NOWY`:** `jednostka = obca_jednostka`; `afiliuje = False`.
- `Patent.wydzial` = `aktualna_jednostka` **pierwszego** (wg kolejności w
  `inventors`) dopasowanego twórcy, którego `aktualna_jednostka` należy do
  naszej Uczelni; jeśli takiego brak → `wydzial = None`.

## 6. Obsługa rekordów niepewnych (wstrzymanie)

Patent jest tworzony **tylko** gdy **wszyscy** jego twórcy rozstrzygnięci
(każdy string ma `decyzja` = pk lub `NOWY`). Jeśli którykolwiek twórca ma
`decyzja` puste → patent dostaje status **`WSTRZYMANY`** w
`patenty_do_przegladu.csv` (z nazwą blokującego twórcy), jest pomijany i
zaimportuje się czysto przy kolejnym `apply` po uzupełnieniu braku. Re-run jest
bezpieczny i przyrostowy.

## 7. Mapowanie pól `Patent`

| Pole BPP                | Źródło                                                         |
|-------------------------|----------------------------------------------------------------|
| `tytul_oryginalny`      | `title`                                                        |
| `rok`                   | rok z `application_date` (zawsze)                              |
| `numer_zgloszenia`      | `application_number` (`P.445383`), może być puste             |
| `data_zgloszenia`       | `application_date` (parsuj `DD-MM-YYYY`), null jeśli brak      |
| `numer_prawa_wylacznego`| `all_fields["Numer patentu/prawa"]` (`Pat.247645`)            |
| `data_decyzji`          | `all_fields["Data udzielenia prawa"]`, null jeśli brak        |
| `wydzial`               | patrz §5.4                                                     |
| `www`                   | `source_url`                                                   |
| `informacja_z`          | `PPM:<source_id>` (audyt + fallback idempotencji)             |
| `charakter_formalny`    | auto (`PAT`) — `cached_property` modelu                       |
| `jezyk`                 | auto (polski) — `cached_property` modelu                      |
| `szczegoly`             | tytuł ang., MKP/IPC (złączone), patent_score — zwięźle        |
| `adnotacje`             | abstrakt PL/EN (jeśli obecne), surowe `all_fields` istotne    |
| twórcy → `Patent_Autor` | `dodaj_autora(...)` w kolejności `inventors`; `zapisany_jako` = oryginalny string |

Parsowanie dat: format źródłowy `DD-MM-YYYY`. Braki/nieparsowalne → `None`
(pola nullable), nigdy wyjątek wywalający cały import.

### Idempotencja (klucz re-run)
Dla każdego rekordu wyznacz klucz:
1. jeśli `numer_zgloszenia` niepuste → szukaj
   `Patent.objects.filter(numer_zgloszenia=...)`;
2. inaczej → szukaj po `informacja_z = "PPM:<source_id>"`.

Jeśli istnieje dokładnie jeden → **update** (aktualizuj pola skalarne;
twórców synchronizuj: usuń dotychczasowe `Patent_Autor` i odtwórz z decyzji —
prościej i deterministycznie niż diff). Jeśli zero → **create**. Jeśli >1 →
`WSTRZYMANY` z powodem „niejednoznaczny klucz" (nie zgadujemy).

## 8. Testy (TDD)

`model_bakery` na istniejących `Autor`/`Jednostka`/`Uczelnia`; mały fixture
sqlite w tmp z ręcznie zbudowanymi blobami `parsed_json` pokrywającymi:

1. dopasowanie `DOKLADNE` (prefill pk),
2. dopasowanie `LUZNE` (kandydat, ale nie prefill),
3. `BRAK` → `NOWY` (tworzenie `Autor` + `obca_jednostka`, `afiliuje=False`),
4. brak `application_number` → klucz z `source_id` w `informacja_z`,
5. nazwisko łącznikowe (`Kukuła-Koch`) — poprawny split,
6. dwie pisownie tego samego (`Kowalski`/`Kovalski`) mapowane na ten sam pk,
7. patent z nierozstrzygniętym twórcą → `WSTRZYMANY`, brak utworzenia,
8. idempotencja: drugi `apply` nie duplikuje, aktualizuje,
9. `--dry-run` nic nie utrwala.

Testy czyste (`test_author_names`, IO CSV, agregacja distinct) bez bazy; testy
`scan`/`apply` z `@pytest.mark.django_db`. `wydzial` = jednostka 1. twórcy z
uczelni — osobny przypadek.

## 9. Rejestracja i uruchamianie

- Dodać `import_sqlite` do `INSTALLED_APPS` w `src/django_bpp/settings/base.py`.
- Bez migracji (apka nie ma modeli) — ale dopisać do `packages.find.include`
  w `pyproject.toml`, jeśli apka ma być w buildzie (spójność z resztą listy).
- Uruchamianie: przeciw żywej bazie BPP (Komparator wymaga Postgresa z pg_trgm
  i wypełnionej tabeli `Autor`). Lokalnie: `run-site` / dump; dla realnego
  importu — baza docelowa.

## 10. Poza zakresem (YAGNI)

- Handlery dla typów innych niż `patent` (w bazie ich nie ma).
- UI webowe / rozszerzanie `importer_publikacji`.
- Fuzzy-matching tekstu „owner_unit" do `Jednostka` (zastąpione regułą §5.4).
- Wpychanie `patent_score` w pola punktowe (liczy BPP wg dyscyplin).
- Ekstrakcja `bpp-core` / instalowalny pakiet (sprzężenie runtime i tak by
  zostało; ogromny refactor bez zysku dla tego zadania).
