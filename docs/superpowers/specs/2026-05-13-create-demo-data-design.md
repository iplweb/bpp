# Specyfikacja: `create_demo_data` + `cleanup_demo_data`

**Data:** 2026-05-13
**Status:** draft — zaakceptowany do implementacji
**Autor:** Michał Pasternak + sesja brainstormingowa Claude'a

## 1. Cel

Dwie management commands służące do (a) wygenerowania reprezentatywnego,
parametryzowalnego zestawu danych demo w bazie BPP oraz (b) całkowitego
ich usunięcia przez manifest. Zaprojektowane jako **dev/test tool** — z
safety guardami chroniącymi przed odpaleniem w produkcji.

Zastosowania:

- ręczne testowanie UI/UX z realistyczną skalą danych,
- testowanie performance'u (10k+ prac w bazie),
- onboarding nowych deweloperów (jedna komenda → "wygląda jak prawdziwa
  uczelnia"),
- repro buga gdy "u mnie działa, bo mam tylko 5 prac".

## 2. Założenia wstępne i pre-flight checks

Komenda **przed pierwszym promptem** weryfikuje obecność wymaganych
danych słownikowych. Failuje wcześnie, z czytelną instrukcją "co
załadować" — żeby nie tracić czasu usera na potwierdzanie i odkrywać
braki dopiero w trakcie generowania.

**Wymagane fixtury słownikowe** (sprawdzane przez `Model.objects.exists()`):

- `Charakter_Formalny`
- `Typ_KBN`
- `Jezyk`
- `Status_Korekty`
- `Rodzaj_Zrodla`
- `Funkcja_Autora`
- `Typ_Odpowiedzialnosci` (v2)
- `Tytul`
- `Plec`
- `Zrodlo_Informacji`
- `Dyscyplina_Naukowa`

Wszystkie te modele są ładowane przez standardowe fixtury z
`src/bpp/fixtures/` lub przez seed dyscyplin (zewnętrzny). Komenda **nie
generuje** żadnego z nich.

**Uczelnia (singleton)** — opcjonalna: jeśli brak, komenda tworzy
`Demo — Uczelnia Testowa` i wpisuje do manifestu z flagą
`created_by_demo: true` (cleanup ją usunie). Jeśli istnieje — reuse,
manifest tej Uczelni nie tknie.

## 3. CLI

### Tworzenie

```bash
uv run python src/manage.py create_demo_data \
    [--wydzialow 10] \
    [--jednostek-na-wydzial 5] \
    [--autorow 500] \
    [--ile-ciaglych 5000] [--ile-zwartych 5000] \
    [--od-roku 2017] [--do-roku 2025] \
    [--procent-z-dyscyplina 80] \
    [--procent-z-subdyscyplina 20] \
    [--procent-zmiana-dyscypliny 10] \
    [--zrodel 50] [--wydawcow 20] \
    [--seed 12345] \
    [--manifest-out <path>] \
    [--batch-size 500] \
    [--yes-i-am-sure --confirm-db <NAME>]
```

### Sprzątanie

```bash
uv run python src/manage.py cleanup_demo_data \
    --manifest <path> \
    [--yes-i-am-sure --confirm-db <NAME>]
```

## 4. Safety — podwójne potwierdzenie

Bez flag CLI komenda zatrzymuje się dwukrotnie:

1. **Prompt 1** — `Stworzy: 10 wydz., 50 jedn., 500 aut., 10000 prac w
   bazie 'bpp'. Kontynuować? [tak/nie]:` — wymaga `tak`
   (case-insensitive).
2. **Prompt 2** — `Aby potwierdzić, wpisz dokładnie nazwę bazy: 'bpp':`
   — wymaga **exact match** (case-sensitive) z
   `connection.settings_dict['NAME']`. Blokuje enter-spam, bo wymaga
   świadomego ręcznego wpisania.

Non-tty (CI, pipe, brak `stdin.isatty()`) → fail z `Brak TTY. Użyj
'--yes-i-am-sure --confirm-db <NAME>'`. Cleanup analogicznie.

## 5. Zakres generowanych obiektów

| Model | Liczba (default) | Konwencja nazw / pól | Do manifestu |
|---|---|---|---|
| `Uczelnia` (singleton) | 0 lub 1 | `Demo — Uczelnia Testowa` (tylko jeśli brak) | tak (z `created_by_demo: true`) |
| `Wydzial` | 10 | `Demo — Wydział <i> (<kierunek>)` | tak |
| `Jednostka` | 10×5 = 50 | `Demo — Jednostka <i>-<j>` | tak |
| `Autor` | 500 | `<imię_pol> <nazwisko_pol>` (random z list konstant) | tak |
| `Autor_Jednostka` | 500 | 1:1 z autorami (1 jednostka per autor) | tak |
| `Autor_Dyscyplina` | ~3600 | per (autor, rok) — według procentów z CLI | tak |
| `Zrodlo` | 50 | `Demo — Czasopismo <i>` + losowy `Rodzaj_Zrodla`, syntetyczny ISSN | tak |
| `Wydawca` | 20 | `Demo — Wydawca <i>` | tak |
| `Wydawnictwo_Ciagle` | 5000 | random tytuł, losowy `Charakter_Formalny` "do ciągłych", rok 2017–2025, losowy `Zrodlo`, punktacja 5–200, losowy DOI, losowe flagi OpenAccess, 1–8 autorów | tak |
| `Wydawnictwo_Ciagle_Autor` | ~22 500 | M2M-through | tak |
| `Wydawnictwo_Zwarte` | 5000 | jak wyżej (z DOI + OA); dla ~20% rozdziały → `wydawnictwo_nadrzedne` (też w manifeście) | tak |
| `Wydawnictwo_Zwarte_Autor` | ~22 500 | M2M-through | tak |

**Pola dodatkowe prac:**

- **DOI**: random, format `10.<4-cyfry>/demo.<rok>.<i>` (syntetyczny ale
  parser-zgodny).
- **OpenAccess flagi**: losowy wybór z `Tryb_OpenAccess_*`, `Wersja_Tekstu_*`,
  `Licencja_OpenAccess` (jeśli wgrane w bazie). Jeśli brak słowników OA →
  pole pozostaje puste (nie wymagane).
- **PBN UID**: **nigdy nie ustawiane** (zostaje puste/null).
- **Procent_Odpowiedzialnosci**: domyślne wartości z `Typ_Odpowiedzialnosci`.

Polskie imiona/nazwiska/kierunki — w stałych modułu
`src/bpp/demo_data/names.py` (lista ~200 imion + ~500 nazwisk + ~30
kierunków studiów; data-only, bez Fakera).

## 6. Manifest

```json
{
  "created_at": "2026-05-13T19:45:00+02:00",
  "command_args": {"wydzialow": 10, "...": "..."},
  "database": "bpp",
  "objects": {
    "bpp.Uczelnia":             {"pks": [1], "created_by_demo": true},
    "bpp.Wydzial":              {"pks": [...]},
    "bpp.Jednostka":            {"pks": [...]},
    "bpp.Autor":                {"pks": [...]},
    "bpp.Autor_Jednostka":      {"pks": [...]},
    "bpp.Autor_Dyscyplina":     {"pks": [...]},
    "bpp.Zrodlo":               {"pks": [...]},
    "bpp.Wydawca":              {"pks": [...]},
    "bpp.Wydawnictwo_Ciagle":   {"pks": [...]},
    "bpp.Wydawnictwo_Ciagle_Autor": {"pks": [...]},
    "bpp.Wydawnictwo_Zwarte":   {"pks": [...]},
    "bpp.Wydawnictwo_Zwarte_Autor": {"pks": [...]}
  }
}
```

- Default path: `./demo_data_manifest_<YYYYMMDD_HHMMSS>.json`.
- **Atomic write** (`.tmp` → `os.replace`) po każdym batch'u → padnięta
  komenda zostawia spójny manifest do cleanup.

## 7. Atomicity i performance

- **Batch commits** po `--batch-size` (default 500) obiektów:
  `@transaction.atomic` per batch, **nie globalnie**.
- `bulk_create(objs, batch_size=...)` zamiast `.save()` per obiekt.
- `tqdm` na **każdej fazie**: tworzenie wydziałów, jednostek, autorów,
  dyscyplin per rok, źródeł, wydawców, prac WC, prac WZ, powiązań
  autorów. ~9 pasków łącznie (sekwencyjnie).
- **Seed**: `--seed N` → deterministyczny output
  (`random.Random(seed)` przekazany do generatorów, **nie globalny**
  `random`).

## 8. Architektura kodu

```
src/bpp/
  demo_data/                     ← NOWY podpakiet
    __init__.py
    names.py                     ← IMIONA_POL, NAZWISKA_POL, KIERUNKI_POL
    manifest.py                  ← Manifest.load/save/append/atomic_write
    confirm.py                   ← double_confirm(stdin, stdout, db_name)
    progress.py                  ← cienka fasada nad tqdm (mockable)
    preflight.py                 ← check_required_dictionaries() → list[str]
    generators/
      __init__.py
      uczelnia.py                ← ensure_uczelnia(manifest, rng)
      wydzialy.py                ← create_wydzialy(n, uczelnia, manifest, ...)
      jednostki.py
      autorzy.py
      dyscypliny.py              ← per-rok generator, według procentów
      zrodla.py
      wydawcy.py
      wydawnictwa.py             ← WC + WZ + powiązania + DOI + OA flagi
  management/commands/
    create_demo_data.py          ← thin entry: parse args → preflight →
                                   confirm → orkiestracja generatorów
    cleanup_demo_data.py         ← thin entry: parse args → confirm →
                                   load → delete
```

Każdy generator dostaje `(manifest, rng, progress_bar_factory)` —
testowalny jednostkowo bez subprocess.

## 9. Cleanup — kolejność usuwania

Explicit, od najbardziej zależnych do najmniej:

1. `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor` (M2M through)
2. `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte` — rozdziały (te z
   `wydawnictwo_nadrzedne != NULL`) **przed** nadrzędnymi
3. `Autor_Dyscyplina`, `Autor_Jednostka`
4. `Autor`, `Jednostka`, `Wydzial`
5. `Zrodlo`, `Wydawca`
6. `Uczelnia` — **tylko jeśli** `created_by_demo: true` w manifeście

Każda faza z tqdm. Cleanup w batch commits
(`pk__in=batch_pks` + `.delete()`). Po sukcesie: rename manifest →
`<original>.applied.<timestamp>.json` (żeby nie odpalić cleanup
dwukrotnie na tym samym manifeście).

## 10. Testy

`src/bpp/tests/test_demo_data.py` (pytest,
`@pytest.mark.django_db(transaction=True)`):

- `test_smoke_minimal` — `--wydzialow 1 --jednostek-na-wydzial 1
  --autorow 5 --ile-ciaglych 5 --ile-zwartych 5 --seed 1
  --yes-i-am-sure --confirm-db <test_db>`. Asercje: manifest pisany,
  obiekty istnieją, liczby się zgadzają.
- `test_cleanup_roundtrip` — utwórz obiekt-świadka przed testem;
  create_demo_data → cleanup_demo_data; obiekt-świadek istnieje,
  demo-obiekty zniknięte.
- `test_seed_determinism` — ten sam seed → te same nazwy obiektów.
- `test_dwa_prompty_blokuja_nie` — symuluj stdin `"nie\n"` → exit 1,
  zero obiektów.
- `test_drugi_prompt_blokuje_zla_nazwe` — stdin `"tak\nbledna_nazwa\n"`
  → exit 1.
- `test_non_tty_wymaga_flag` — non-tty bez `--yes-i-am-sure` → exit 1 z
  czytelnym message.
- `test_preflight_brak_dyscyplin` — w bazie brak `Dyscyplina_Naukowa` →
  exit 1, instrukcja jak załadować. Komenda **nie pyta** o
  potwierdzenie (preflight wyprzedza prompty).
- `test_preflight_brak_charakter_formalny` — analogicznie dla
  `Charakter_Formalny`.
- `test_manifest_atomic_write` — pad pomiędzy batchami (mock raising w
  generator) → manifest zawiera tylko zacommitowane batchy, cleanup je
  posprząta.
- `test_doi_format` — każda praca ma DOI w formacie
  `10.<4-cyfry>/demo.<rok>.<i>`.
- `test_openaccess_losowe_jak_slowniki_sa` — jeśli słowniki OA w bazie
  → ~połowa prac ma ustawione tryb/wersja/licencja.
- `test_openaccess_puste_jak_slownikow_brak` — bez słowników OA →
  pola NULL, brak crash.
- `test_pbn_uid_zawsze_puste` — wszystkie prace mają puste PBN UID.

## 11. Out of scope (v1)

**Nie generujemy:**

- Konferencje (`Konferencja`)
- Patenty (`Patent`)
- Prace doktorskie (`Praca_Doktorska`)
- Prace habilitacyjne (`Praca_Habilitacyjna`)
- Grants (`Grant`)
- Nagrody (`Nagroda`)
- Serie wydawnicze (`Seria_Wydawnicza`)
- Kierunki studiów, koła naukowe
- Repozytorium

**Nie ustawiamy:**

- PBN UID-y (zawsze puste/null — wymagane przez usera)
- Customowy procent_odpowiedzialnosci (zostają defaulty)
- Cykl ewaluacyjny 2017–2021 jako policzone sloty
- Punktacje źródła (`Punktacja_Zrodla`) — używamy losowych wartości
  w `impact_factor`/`punktacja_wewnetrzna` pól pracy, ale tabel
  punktacji per rok nie generujemy

**Inne:**

- Re-run safety (komenda nie obsługuje "tylko dopisz X autorów do
  istniejącego manifestu" — każde uruchomienie tworzy nowy manifest)
- Multi-database (operuje tylko na `default`)

## 12. Słowniki — out of scope w manifeście

Wszystkie obiekty słownikowe wymienione w sekcji 2 nigdy nie trafiają
do manifestu i nigdy nie są usuwane przez cleanup. Są danymi bazowymi
ładowanymi raz przez fixtury / seed dyscyplin, niezależnie od demo
data. Pre-flight check (sekcja 2) gwarantuje, że są obecne **przed**
rozpoczęciem generowania.

## 13. Decyzje odrzucone (z trade-offami)

- **Faker** — odrzucone, bo wymagałoby nowej dev-dependency, a
  Faker'owe polskie locale ma mniej kontroli niż własne listy
  imion/nazwisk.
- **Fixture Django (loaddata-able JSON)** — odrzucone w pytaniu 1; user
  wybrał manifest cleanup (lekki format).
- **CASCADE-cleanup** — odrzucone w pytaniu 10; user wybrał explicit
  cleanup (bezpieczniejsze, nie tknie obiektów dopiętych ręcznie).
- **Jedna transakcja na całość** — odrzucone w pytaniu 12; user wybrał
  batch commits + progress (lepszy UX dla 20k+ obiektów).
- **Generowanie dyscyplin** — odrzucone (muszą być w bazie; weryfikuje
  pre-flight).
- **Generowanie Uczelni gdy istnieje** — odrzucone (singleton, reuse
  jeśli jest).

## 14. Definicja sukcesu (acceptance)

- `uv run python src/manage.py create_demo_data --yes-i-am-sure
  --confirm-db <NAME>` z domyślnymi parametrami:
  - na bazie z wgranymi fixturami + dyscyplinami → tworzy obiekty,
    zapisuje manifest, exit 0;
  - na bazie bez dyscyplin → fail z instrukcją, exit 1, zero obiektów
    w bazie;
  - bez flag (interaktywnie) → dwa prompty, drugi wymaga exact DB
    name;
  - non-tty bez flag → fail z instrukcją.
- `uv run python src/manage.py cleanup_demo_data --manifest <path>
  --yes-i-am-sure --confirm-db <NAME>`:
  - usuwa **wszystkie** obiekty z manifestu, exit 0;
  - obiekty utworzone poza demo (świadkowie) pozostają nietknięte;
  - manifest jest renamowany na `.applied.*`.
- Wszystkie testy z sekcji 10 przechodzą.
- `ruff format` i `ruff check` przechodzą bez błędów.
- `pre-commit` przechodzi.
