# Import z plików SQLite (`import_sqlite`)

Aplikacja `import_sqlite` importuje dane z lokalnych plików **SQLite**
wyprodukowanych przez zewnętrzne **harvestery** (narzędzia, które zbierają
rekordy z portali bibliograficznych i zapisują je offline). Pierwszy i obecnie
jedyny obsługiwany typ rekordu to **patenty**.

Aplikacja mieszka w repozytorium (`src/import_sqlite/`), nie ma własnych modeli
i nie tworzy migracji — całą pracę wykonują dwa polecenia zarządzania plus
edytowalne pliki CSV, w których człowiek podejmuje decyzje o dopasowaniu
twórców.

## Format wejściowy

Harvester zapisuje rekordy do tabeli `records` w pliku SQLite. Import czyta
z niej trzy kolumny:

| kolumna       | znaczenie                                            |
|---------------|------------------------------------------------------|
| `type`        | rodzaj rekordu (np. `patent`) — import filtruje po nim |
| `source_id`   | stabilny identyfikator rekordu po stronie źródła      |
| `source_url`  | adres strony szczegółów rekordu                       |
| `parsed_json` | wyekstrahowane pola rekordu jako JSON                 |

Warstwa czytająca (`reader.py`) jest **generyczna** — filtruje wyłącznie po
kolumnie `type`. Mapowanie `parsed_json` na konkretny model BPP robi *handler*
danego typu (`handlers/patent.py`). Rekordy z pustym lub niepoprawnym
`parsed_json` są pomijane z ostrzeżeniem, bez przerywania importu.

## Dwie fazy: `scan` → (ręczne uzgodnienie) → `apply`

Import jest celowo dwufazowy. Faza `scan` niczego nie zapisuje do bazy — tylko
proponuje dopasowania twórców i wypisuje je do CSV. Człowiek przegląda i
zatwierdza, a dopiero `apply` tworzy rekordy.

```bash
# Faza 1 — skan: czyta SQLite, dopasowuje twórców, wypisuje CSV-e
uv run python src/manage.py import_sqlite_scan \
    /sciezka/do/pliku.sqlite3 --typ patent \
    --out-autorzy autorzy_do_uzgodnienia.csv \
    --out-patenty patenty_do_przegladu.csv

#  ← edytujesz autorzy_do_uzgodnienia.csv (wypełniasz kolumnę `decyzja`)

# Faza 2 — podgląd bez zapisu (transakcja wycofywana na końcu)
uv run python src/manage.py import_sqlite_apply \
    /sciezka/do/pliku.sqlite3 --typ patent \
    --autorzy autorzy_do_uzgodnienia.csv --dry-run

# Faza 2 — właściwy import (bez --dry-run)
uv run python src/manage.py import_sqlite_apply \
    /sciezka/do/pliku.sqlite3 --typ patent \
    --autorzy autorzy_do_uzgodnienia.csv
```

Oba polecenia są **idempotentne** i **wznawialne**: po uzupełnieniu braków w
CSV kolejny `apply` doimportowuje resztę, a rekordy już istniejące
aktualizuje zamiast duplikować.

## Dopasowanie twórców (rdzeń narzędzia)

Twórcy w źródle to zwykłe napisy `"Imię Nazwisko"`. Zamiast dopasowywać każde
wystąpienie z osobna, `scan` zbiera **zbiór unikalnych napisów nazwisk** ze
wszystkich rekordów i dopasowuje każdy z nich **raz**, reużywając komparatora
autorów BPP (`crossref_bpp.Komparator`). Jedna Twoja decyzja rozprowadza się
potem na **wszystkie** rekordy zawierające ten napis.

Wynik trafia do `autorzy_do_uzgodnienia.csv` — jeden wiersz na unikalny napis:

| kolumna             | znaczenie                                                     |
|---------------------|---------------------------------------------------------------|
| `nazwisko_zrodlowe` | oryginalny napis z pola twórców (klucz wiersza)               |
| `given`, `family`   | wynik podziału napisu na imię i nazwisko                       |
| `wystapien`         | w ilu rekordach ten napis występuje                          |
| `status`            | jakość dopasowania (niżej)                                    |
| `kandydat_1..3`     | najlepsi kandydaci: `Nazwisko Imię (#pk, pewność, N publ.)`   |
| `decyzja`           | **wypełnia człowiek**                                          |

Statusy dopasowania:

- **DOKLADNE** — jednoznaczne trafienie; kolumna `decyzja` jest **wstępnie
  wypełniona** identyfikatorem (pk) dopasowanego autora. Zwykle nie ruszasz.
- **LUZNE** / **WYMAGA_INGERENCJI** — jest kandydat (lub kilku), ale
  potwierdzenie należy do Ciebie; `decyzja` startuje pusta.
- **BRAK** — brak dopasowania; decydujesz Ty.

Semantyka kolumny `decyzja`:

- **pk autora** (liczba, np. `441`) → przypisz ten napis do istniejącego autora;
- **`NOWY`** → utwórz nowego autora (imię/nazwisko z podziału napisu),
  przypisanego do „obcej jednostki" uczelni, bez afiliacji;
- **puste** → napis **nierozstrzygnięty** (rekord z takim twórcą zostanie
  wstrzymany, patrz niżej).

### Spójne dopasowanie mimo literówek

Plik `autorzy_do_uzgodnienia.csv` jest **posortowany po znormalizowanym
nazwisku** (bez diakrytyków, `ł`→`l`, bez wielkości liter). Dzięki temu różne
pisownie tego samego człowieka (np. `Kowalski Jan` i `Kovalski Jan`) lądują
**obok siebie** — widzisz rozjazd i możesz skierować obie decyzje na **ten sam
pk**. Dwie pisownie zlewają się wtedy w jednego autora, spójnie we wszystkich
rekordach.

## Co powstaje w bazie (patenty)

Handler patentów tworzy rekord `Patent` i powiązania `Patent_Autor`. Mapowanie
najważniejszych pól:

| Pole BPP                 | Źródło                                                       |
|--------------------------|--------------------------------------------------------------|
| `tytul_oryginalny`       | tytuł rekordu (przepuszczony przez sanityzację HTML)         |
| `rok`                    | rok z daty zgłoszenia, a gdy brak — rok z daty udzielenia    |
| `numer_zgloszenia`       | numer zgłoszenia (może być pusty)                            |
| `data_zgloszenia`        | data zgłoszenia                                             |
| `numer_prawa_wylacznego` | numer prawa/patentu — **klucz idempotencji**                |
| `data_decyzji`           | data udzielenia prawa                                       |
| `wydzial`                | jednostka pierwszego dopasowanego twórcy będącego pracownikiem uczelni |
| `www`                    | adres źródła (nośnik proweniencji)                          |
| `informacja_z`           | słownikowy wpis „źródło importu" (audyt)                    |
| `szczegoly` / `adnotacje`| tytuł obcojęzyczny, klasyfikacje, opisy                     |
| twórcy → `Patent_Autor`  | w kolejności ze źródła, z zachowaniem oryginalnego napisu jako „zapisany jako" |

Afiliacja twórcy zależy wyłącznie od tego, czy jego jednostka skupia
pracowników uczelni (twórcy z „obcej jednostki" są nieafiliowani).

### Idempotencja i aktualizacja

Kluczem ponownego uruchomienia jest `numer_prawa_wylacznego`:

- **brak** takiego rekordu → tworzony jest nowy patent;
- **jeden** istniejący → **aktualizacja** (pola skalarne nadpisywane danymi ze
  źródła; powiązania twórców odtwarzane od nowa — import jest źródłem prawdy dla
  tych rekordów);
- **więcej niż jeden** → rekord wstrzymany („niejednoznaczny klucz"), bez
  zgadywania.

## Rekordy wstrzymane

Rekord jest **wstrzymywany** (pomijany, z powodem wypisanym w
`patenty_do_przegladu.csv`) i zaimportuje się przy kolejnym `apply` po naprawie,
gdy:

- którykolwiek twórca ma pustą `decyzja` (nierozstrzygnięty);
- utworzenie powiązania twórcy narusza reguły walidacji (np. wymóg afiliacji);
- klucz idempotencji trafia w więcej niż jeden istniejący rekord.

Cały `apply` biegnie w jednej transakcji, a każdy rekord w **osobnym
savepoincie** — wstrzymanie jednego nie cofa reszty. `--dry-run` wykonuje pełne
przetworzenie i na końcu **wycofuje** całą transakcję, więc możesz obejrzeć
wynik (statusy w `patenty_do_przegladu.csv`) bez zapisu do bazy.

## Wymagania uruchomieniowe

- Komparator autorów odpytuje bazę (dopasowania po tabeli autorów), więc oba
  polecenia wymagają **żywej bazy BPP**. Lokalnie najprościej przez `run-site`
  (ewentualnie z wczytanym zrzutem prawdziwej bazy), a dla właściwego importu —
  baza docelowa.
- Uczelnia musi mieć ustawioną „obcą jednostkę" (używaną dla twórców spoza
  uczelni oraz dla nowo tworzonych autorów) — inaczej `apply` pada czytelnym
  komunikatem na starcie, zamiast błędem w środku importu.

## Rozszerzanie o kolejne typy

Warstwa czytająca SQLite jest niezależna od typu. Aby dołożyć obsługę nowego
rodzaju rekordu (np. innego niż patent), dopisz handler w `handlers/`
(parsowanie `parsed_json` → obiekt danych + materializacja do modelu BPP) i
podłącz go pod polecenia. Obecnie zaimplementowany jest wyłącznie typ `patent`.

## Struktura kodu

```
src/import_sqlite/
    reader.py                    # generyczny czytnik tabeli `records`
    core/author_names.py         # podział i normalizacja napisów nazwisk
    core/author_matching.py      # dopasowanie (Komparator) + agregacja unikalnych
    review_io.py                 # zapis/odczyt plików CSV przeglądu
    handlers/patent.py           # parsowanie patentu + materializacja do BPP
    management/commands/
        import_sqlite_scan.py    # faza 1
        import_sqlite_apply.py   # faza 2
```

Projekt techniczny i plan implementacji: `docs/superpowers/specs/` oraz
`docs/superpowers/plans/` (pliki `*import-sqlite*`).
