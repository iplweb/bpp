# Spec: testy samowystarczalne (nie zakładaj baseline)

Status: **A zaimplementowane, B w toku** · Autor: audyt izolacji testów ·
Data: 2026-07-13

## 1. Problem i udowodniony root cause

Część testów zakłada, że dane referencyjne (słowniki: `RodzajJednostki`,
`Jezyk`, `Funkcja_Autora`, `Crossref_Mapper`, `Rzeczownik`, `Tytul`, …) **są
już w bazie** — bo baseline (`baseline.sql`) i migracje danych je seedują.

### Mechanizm flake'a (zdiagnozowany instrumentacją, nie zgadnięty)

1. Testy `transactional_db`/`transaction=True` na teardownie
   (`_fixture_teardown` w `src/conftest.py`) robią `flush` → `TRUNCATE ...
   CASCADE` całej bazy. Instrumentacja dowiodła: `RodzajJednostki` PK
   `przed=[1,2,3] po=[]`.
2. `flush` emituje `post_migrate` (`inhibit_post_migrate=False`), ale słowniki
   seedowane **migracjami danych** (0449, 0467, 0035, …) **nie mają receivera**
   — więc NIE wracają. To nie prawo natury, tylko **brakujący receiver**: repo
   już ma ten wzorzec dla grup (`odtworz_grupy`) i raportów (`seed_reports`).
3. **Dlaczego zielono lokalnie, a flake na CI:** lokalnie warstwa testcontainers
   przeładowuje baseline między testami (dowód: PK/xmin pokazują re-insert z
   oryginalnymi PK dla testów nie-transakcyjnych — fixture `db`). Na CI
   (`PYTEST_TESTCONTAINERS_DISABLE=1`, template-clone `bpp` z osobnego
   `iplweb/bpp_dbserver`) tej warstwy nie ma → po flushu słowniki zostają puste
   → kolejny test na tym samym workerze (pytest-split, `-n auto`) widzi pustą
   tabelę → `DoesNotExist` / `count()==0` / błędna decyzja pipeline'u.

To NIE „inny sposób ładowania bazy" — to **brak per-test restore baseline na CI**
w połączeniu z **brakiem receivera** dla słowników migracyjnych.

### Dwie osie kruchości

1. **CI-flake (tu i teraz).** j.w.
2. **Dług długoterminowy.** „Zakładam, że X jest w bazie" psuje się przy każdej
   zmianie baseline/migracji/kolejności. Test nie mówi, czego potrzebuje.

### Fix A (zaimplementowane) — root fix przez `post_migrate`

`bpp/seed_slowniki.py` podpięte pod `post_migrate` (wzorzec `odtworz_grupy`)
odtwarza `RodzajJednostki` po KAŻDYM flushu/migracji — **reużywając oryginalnych
funkcji seedujących migracji** (0449+0454+0464, zero duplikacji/dryfu wartości).
Weryfikacja: dwa kolejne testy transakcyjne — drugi widzi re-seed z poprawnymi
atrybutami (wcześniej `[]`). To gasi flake u źródła dla `RodzajJednostki` na
obu środowiskach, bez tykania testów. Program B (niżej) domyka resztę słowników
tam, gdzie fixtura jest właściwsza niż globalny seed.

### Dowód i miara (B)

Audyt (patrz §3) — wymazanie słowników referencyjnych (poza odtwarzanymi przez
`post_migrate`, w tym `RodzajJednostki` pokryte fixem A) przed każdym testem —
mierzy, ile testów zakłada niedeklarowany słownik. Lista `FAILED` = zakres B.
Wcześniejszy przebieg (przed A): **51 testów w 27 plikach**; aktualny re-audyt
w toku.

## 2. Zasada

> **Test (i kod produkcyjny) nie zakłada, że cokolwiek jest w bazie. Każdy test
> JAWNIE deklaruje swoje dane referencyjne przez fixtury.**

Konsekwencje:

- `Model.objects.get(nazwa=…)` na słowniku referencyjnym = **zapach**.
  Zamiast tego: `get_or_create`, funkcja seedująca, albo fixtura.
- Fixtury referencyjne są **jawne i deklaratywne** — nawet jeśli test ciągnie
  composite `wspolne_dane` (bundlujący 10 innych fixtur), z listy fixtur w
  sygnaturze testu **widać, czego wymaga**.
- Preferujemy **idempotentny `get_or_create`** (additywny — nie bije się z
  danymi innych fixtur), a nie „delete-then-seed" (chyba że test wymaga
  DOKŁADNIE znanego zbioru).
- Fixtury **reużywają funkcji seedujących z migracji** (np.
  `seed_rodzajjednostki`, `seed_crossref_mapper_rows`) zamiast duplikować dane —
  jedno źródło prawdy.

## 3. Metodologia audytu (reużywalna)

Flaga `AUDIT_WIPE_REFERENCE=1` (tymczasowy kod w `src/conftest.py`, NIE
commitowany na stałe) wymiata przed każdym testem wszystkie niepuste tabele
spoza `django_*`/`auth_*`/`social_*` (przez osobne autocommit-połączenie,
`session_replication_role=replica` dla FK). Uruchomienie:

```bash
AUDIT_WIPE_REFERENCE=1 PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest src/ \
  --ignore=src/integration_tests --ignore=src/bpp/tests/test_playwright \
  -n 4 -p no:randomly -q --tb=no
```

Lista `FAILED`/`ERROR` = testy zakładające baseline. To **kryterium akceptacji**
(§8): po pracy ta lista jest pusta (poza świadomie wykluczonymi — patrz §7).

## 4. Zakres (51 testów, 27 plików — kategorie)

| Kategoria | ~testów | Brakujący słownik | Główna dźwignia |
|---|---|---|---|
| RodzajJednostki „Wydział"/„Koło naukowe" | ~25 | `RodzajJednostki` | fixtura `wezel` + komenda `konwertuj_wydzialy` + bezpośrednie `.get` |
| Jezyk „polski" | ~7 | `Jezyk` | helper `get_jezyk_polski`/`pobierz_jezyk` (produkcja) + testy |
| Rzeczownik (nazwy/menu/cache) | ~4 | `Rzeczownik` | fixtura `rzeczowniki` |
| Uczelnia (scope/ranking) | ~4 | `Uczelnia`/struktura | fixtury per-uczelnia |
| Crossref/Funkcja/import | ~5 | `Crossref_Mapper`, `Funkcja_Autora` | seed w teście/fixturze |
| „Testy-o-seedzie/migracji" | ~6 | — | patrz §7 (zapewniają, nie naprawiają) |

Pełna lista 51 testów: w `docs/deweloper/spec-testy-samowystarczalne-lista.txt`
(generowana z audytu; do wygenerowania przy starcie prac).

## 5. Projekt fixtur

### 5.1 Fixtury per-słownik (jawne)

Lokalizacja: `src/fixtures/conftest_system.py` (gdzie żyją już `jezyki`,
`charaktery_formalne`). Nowe/uzupełnione, wszystkie **idempotentne**:

- `rodzaje_jednostek` — `get_or_create` „Wydział" (`autor_moze_afiliowac=False`),
  „Koło naukowe" (`wyklucz_z_rankingu_autorow=True`), … Reużywa
  `seed_rodzajjednostki` z migracji 0449 tam, gdzie się da.
- `funkcje_autora` — „asystent", „adiunkt", „profesor", … (reużywa seeda).
- `crossref_mappery` — 16 wierszy (reużywa `seed_crossref_mapper_rows` z 0467).
- `rzeczowniki` — konfiguracja nazw (jednostka/wydział/…), reużywa seeda.
- `tytuly` — „dr"/„doktor", … (reużywa seeda; już częściowo w `_autor_maker`).
- (istniejące) `jezyki`, `charaktery_formalne` — pozostają, ew. ujednolicone
  na `get_or_create`.

### 5.2 Composite `dane_referencyjne` (alias „wspolne_dane")

Fixtura zbiorcza requestująca komplet powyższych — dla testów, które potrzebują
„standardowego" tła referencyjnego, bez wymieniania każdego z osobna:

```python
@pytest.fixture
def dane_referencyjne(
    rodzaje_jednostek, jezyki, charaktery_formalne, funkcje_autora,
    crossref_mappery, rzeczowniki, tytuly,
):
    """Komplet słowników referencyjnych. Test, który to ciągnie, JAWNIE
    deklaruje: 'potrzebuję standardowego tła referencyjnego'."""
```

Zasada wyboru w teście:
- potrzebujesz jednego słownika → request konkretnej fixtury (`rodzaje_jednostek`),
- potrzebujesz szerokiego tła → `dane_referencyjne`.

W obu wypadkach **z sygnatury testu widać, czego wymaga.**

### 5.3 Kod produkcyjny — UWAGA: nie każdy „hard get" to zapach

Rozróżnienie kluczowe (korekta po review): **`.get` w produkcji bywa CELOWY** —
brak wpisu to błąd konfiguracji, który MA rąbnąć głośno, nie być cicho
utworzony.

- `src/pbn_integrator/importer/helpers.py::get_jezyk_polski` — **NIE zmieniać**
  na `get_or_create`. Rzuca `DoesNotExist` świadomie („brak polskiego = błąd
  konfiguracji, zgłoś głośno"). `get_or_create` zamaskowałby realny błąd. Test,
  który tego dotyka, ma zapewnić `Jezyk` fixturą — nie zmieniamy semantyki
  produkcji.
- `src/bpp/management/commands/konwertuj_wydzialy_na_jednostki.py:12` —
  `RodzajJednostki.objects.get(nazwa="Wydział")`: **pokryte fixem A**
  (`post_migrate` odtwarza „Wydział"), więc nie flake'uje. Zmiana na
  `get_or_create` opcjonalna (defensywność), nie wymagana dla stabilności.
- `src/bpp/models/struktura_konwersja.py:77` — `get_or_create(nazwa="Wydział")`
  bez `autor_moze_afiliowac` → dołożyć `defaults` z poprawną flagą (to realne
  drobne uodpornienie; `get_or_create` już jest, brak tylko flagi).

## 6. Wzorce implementacyjne

1. **`.get` → `get_or_create`** na słowniku, z `defaults` gdy liczą się
   atrybuty (np. „Wydział" musi mieć `autor_moze_afiliowac=False`; samo
   `defaults` nie wystarcza, jeśli inny kod utworzył wpis bez flagi — wtedy
   `get_or_create` + wymuszenie flagi, wzorzec z fixtury `kolo_naukowe`).
2. **Reużyj seeda migracji** zamiast duplikować listę wartości.
3. **Nie deletuj** cudzych danych w fixturze (additywnie), chyba że test wymaga
   dokładnego zbioru.
4. **Fixtury lokalne w pliku testowym** (jak `wezel`) — napraw fixturę raz,
   pokrywa całą grupę testów.

## 7. Świadome wykluczenia

Testy, które LEGALNIE weryfikują stan seeda/migracji, **zapewniają** dane
(wołają funkcję seedującą), nie „udają że baseline istnieje":

- `test_migration_0463_multiseek_values`, `test_rodzaj_jednostki::test_seed_*`,
  `test_crossref_mapper_defaults::test_migracja_zaseedowala` — wołają realną
  (idempotentną) funkcję seedującą, potem asertują jej wynik.

## 8. Kryteria akceptacji

1. `AUDIT_WIPE_REFERENCE=1 … pytest` (§3) — **zero** `FAILED`/`ERROR` z tytułu
   braku danych referencyjnych (poza §7, które seedują same).
2. Normalny przebieg (bez flagi) — zielony, bez regresji.
3. `ruff` czysto; newsfragment (`bugfix`).
4. Kod audytu (`AUDIT_WIPE_REFERENCE`) **nie** zostaje w repo (to narzędzie
   diagnostyczne odpalane na żądanie; można je trzymać w tym spec-u).

## 9. Guard V1 (osobna, komplementarna sprawa)

Niezależnie od powyższego zostaje **guard V1** w `src/conftest.py`
(`_neutralizuj_wyciekle_dane`): czyści przed każdym testem DB **nadmiarowe**,
wyciekłe (scommitowane poza rollback) dane domenowe (`bpp_autor`,
`bpp_jednostka`, `bpp_stopiensluzbowy`, `bpp_stanowiskodydaktyczne`,
`bpp_grupa_pracownicza`). Tego testem się nie naprawi (test typu
`test_pusta_baza_zwraca_pusta_liste` wymaga NIEobecności danych). Koszt: 1 tanie
zapytanie/test. Guard V1 dotyczy „za dużo danych"; ten spec — „za mało danych".

## 10. Plan prac (kategoriami, jeden commit per kategoria)

1. `rodzaje_jednostek` + `konwertuj_wydzialy` + `struktura_konwersja` (~25).
2. `jezyki`/`get_jezyk_polski` (~7).
3. `rzeczowniki` (~4).
4. Uczelnia (~4).
5. Crossref/Funkcja/import (~5).
6. `dane_referencyjne` (composite) + podpięcie tam, gdzie test ciągnie szerokie
   tło.
7. Re-audyt (§3) → zielono → newsfragment.
