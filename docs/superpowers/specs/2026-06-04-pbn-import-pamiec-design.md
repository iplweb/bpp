# Redukcja zużycia pamięci w imporcie PBN (`pbn_integrator`)

Data: 2026-06-04
Status: **Do akceptacji.**

## Problem

Import danych z PBN — **w szczególności import źródeł (czasopism)** — powoduje,
że proces zajmuje bardzo dużo pamięci (rzędu gigabajtów), co na maszynach
produkcyjnych prowadzi do OOM / swappingu i wydłuża cały import.

Diagnoza wykazała, że to nie pojedynczy bug, tylko **powtarzalny anty-wzorzec**
rozsiany po `src/pbn_integrator/`: kod materializuje całe tabele modeli-luster
PBN (każdy wiersz z dużym polem JSON) naraz w pamięci Pythona.

## Przyczyna źródłowa

Modele-lustra PBN dziedziczą po `BasePBNMongoDBModel`
(`src/pbn_api/models/base.py:24`) i niosą pole:

```python
versions = JSONField(default=list)   # cała historia wersji rekordu z PBN
```

Dla `Journal` / `Publication` / `Publisher` to wielo-KB do dziesiątek-KB JSON-a
na wiersz (wszystkie wersje, punktacja 2017–2026, dyscypliny). `OswiadczenieInstytucji`
niesie analogicznie `disciplines = JSONField` (`src/pbn_api/models/oswiadczenie_instytucji.py:32`).

Dwa mechanizmy zamieniają „przejdź po tabeli" w „trzymaj całą tabelę JSON-a w RAM":

1. **Cache wyników QuerySet-a.** Iterowanie QuerySet-a
   (`for x in Model.objects.all()`, również opakowane w `tqdm(...)` / `pbar(...)`)
   wywołuje `QuerySet._fetch_all()`, który ładuje **cały** wynik do
   `_result_cache` i trzyma go żywym przez cały czas trwania pętli. Jedyny
   sposób, by tego uniknąć, to `.iterator(chunk_size=N)` (kursor serwerowy,
   bez `_result_cache`) albo w ogóle nie ładować obiektów (`.values_list(...)`).

2. **Trzymanie wszystkich obiektów / future-ów naraz.** Wzorzec
   `journals = list(Model.objects.filter(...))` + `futures = {executor.submit(..., obj): obj ...}`
   przetrzymuje każdy ciężki obiekt **podwójnie** (jako argument zadania i jako
   wartość w słowniku future-ów), żywy aż do końca funkcji. Szczyt ≈ 2× cała
   tabela JSON-a.

## Wzorce naprawcze (kanon)

W repo **już istnieją** poprawne wzorce — naprawa polega na rozszerzeniu ich na
pozostałe miejsca.

### Wzorzec A — lista ID + leniwy `.get()` w workerze

Dla pętli, które realnie potrzebują obiektu modelu (zapis, odczyt JSON-a) i/lub
są zrównoleglone wątkami. Wzorzec referencyjny:
`src/pbn_integrator/utils/source_scoring_import.py:122` oraz — po naprawie —
`importuj_zrodla` (`src/pbn_integrator/importer/sources.py`).

```python
# Zbierz wyłącznie klucze (lekkie stringi 32-znakowe), nigdy całe obiekty:
ids = list(Model.objects.filter(...).values_list("pk", flat=True))
# ...a pełny obiekt (z JSON-em) ładuj leniwie tam, gdzie jest przetwarzany:
for pk in ids:
    obj = Model.objects.get(pk=pk)      # zwolniony zaraz po przetworzeniu
    przetworz(obj)
```

Zaletą wobec `.iterator()` jest **bezpieczeństwo przy zapisie w trakcie pętli**
(lista ID to migawka — nie ma ryzyka kursora serwerowego na modyfikowanej
tabeli) oraz thread-safety (do workera trafia string, nie współdzielony obiekt).

### Wzorzec B — `.values_list(...).iterator(chunk_size=N)`

Dla pętli **tylko do odczytu**, które nie modyfikują iterowanej tabeli i
potrzebują wąskiego zakresu pól:

```python
total = qs.count()
for doi in qs.values_list("doi", flat=True).iterator(chunk_size=500):
    ...
```

`.values_list(...)` pomija instancjonowanie modelu (zero hydratacji JSON-a),
`.iterator()` pomija `_result_cache`.

### Zasada poboczna — `Subquery` zamiast `pk__in=list(...)`

`exclude(pk__in=list(Rekord.objects.values_list("pbn_uid_id", flat=True)))`
ściąga cały zbiór ID do Pythona i wysyła go z powrotem jako parametry SQL.
`exclude(pk__in=Subquery(...))` zostawia wykluczenie po stronie bazy
(wzorzec już użyty w `importuj_zrodla`).

## Inwentarz hotspotów

| # | Lokalizacja | Model (JSON) | Severity | Wzorzec | Status |
|---|-------------|--------------|----------|---------|--------|
| 0 | `importer/sources.py` `importuj_zrodla` | `Journal` (`versions`) | KRYT. | A | ✅ **Zrobione** (branch `feature/pbn-zrodla-mem`) |
| 1 | `importer/__init__.py:122` `importuj_publikacje_instytucji` | `Publication` (`versions`) | WYSOKA | B + Subquery | Do zrobienia |
| 2 | `utils/statements.py:349` `integruj_oswiadczenia_pbn_first_import` | `OswiadczenieInstytucji` (`disciplines`) | WYSOKA | A (zapis w pętli) | Do zrobienia |
| 3 | `utils/statements.py:319` `integruj_oswiadczenia_z_instytucji` | `OswiadczenieInstytucji` | ŚR-WYS | A | Do zrobienia |
| 4 | `importer/publishers.py:164` `importuj_wydawcow` | `Publisher` (`versions`) | ŚREDNIA | B (w `transaction.atomic`) | Do zrobienia |
| 5 | `utils/publications.py:259,300` `pobierz_prace_po_doi/isbn` | `Rekord` (skalarne) | ŚREDNIA | B (`values_list`) | Do zrobienia |

### Miejsca uznane za poprawne (bez zmian)

- `utils/integration.py` `integruj_wszystkie_publikacje` — już
  `list(...values_list("pk"))` + batch-e po 128 ID z leniwym `.get()` w
  workerze. ✅ (drobiazg: słownik future-ów trzyma wszystkie batch-e ID naraz —
  tylko ID, niska waga.)
- `utils/scientists.py` `pobierz_ludzi_z_uczelni` — trzyma wszystkie future-y,
  ale ograniczone rozmiarem odpowiedzi API, a wyniki są odrzucane. ✅
- `utils/threaded_page_getter.py` (faza pobierania) — strumieniowanie
  stron, pamięć ograniczona. ✅

## Zakres / Non-goals

**W zakresie:** punkty 1–5 z inwentarza (punkt 0 już wykonany na osobnym branchu).

**Poza zakresem:**

- Tuning liczby wątków/procesów (osobna dźwignia — mniej workerów = mniej
  obiektów rezydentnych, ale wolniej; do rozważenia tylko gdy 1–5 nie wystarczą).
- Zmiana schematu (np. wyniesienie `versions` do osobnej tabeli / kolumny TOAST
  z `deferred`) — większy, ryzykowny refactor; nie tutaj.
- Faza pobierania (download) — już strumieniowa.

## Ryzyka

1. **Zapis w trakcie iteracji (punkt 2, częściowo 3).**
   `integruj_oswiadczenia_pbn_first_import` w pętli importuje publikacje i może
   wstawiać/modyfikować wiersze. Dlatego **wymusza Wzorzec A** (migawka listy
   ID), nie kursor serwerowy `.iterator()` — kursor na modyfikowanej tabeli to
   proszenie się o niespójność. Dla punktu 3 należy potwierdzić, czy pętla
   wstawia wiersze `OswiadczenieInstytucji`; jeśli nie — `.iterator()` jest OK,
   jeśli tak — Wzorzec A.

2. **`.iterator()` wewnątrz `transaction.atomic` (punkt 4).** W PostgreSQL
   kursor serwerowy działa poprawnie w obrębie transakcji — `importuj_wydawcow`
   jest opakowany w `transaction.atomic()`, więc `.iterator()` jest bezpieczny.

3. **Kolejność wdrażania.** Najpierw najtańsze i najbezpieczniejsze (pętle
   tylko-do-odczytu), na końcu punkt 2 (zapis w pętli). Rekomendowana kolejność:
   **1 → 5 → 4 → 3 → 2**.

## Weryfikacja

Każda zmiana to **refactor zachowujący zachowanie** — siatką bezpieczeństwa jest
test charakteryzujący (zielony przed i po), a sama redukcja pamięci jest
gwarantowana strukturalnie przez diff (`.values_list(...).iterator()` / lista ID
/ `Subquery`). Kontrakty testowe per punkt:

- **Punkt 1:** worker-dyspozytor `importuj_publikacje_po_pbn_uid_id` dostaje
  `mongoId` (string) każdej nie-zaimportowanej publikacji dokładnie raz; już
  zaimportowane (obecne w `Rekord`) są pomijane (re-entrancy).
- **Punkty 2–4:** pętla przetwarza wszystkie wiersze (charakteryzacja: licznik
  wywołań funkcji przetwarzającej == liczba wierszy), kolejność i wynik bez
  zmian.
- **Punkt 5:** zbiór zebranych DOI/ISBN identyczny jak przed zmianą dla tego
  samego zestawu danych wejściowych.

Walidacja pamięci (jednorazowa, manualna — nie test jednostkowy, bo pomiary
pamięci są flaky): na zaseedowanej bazie odpalić krok importu pod
`/usr/bin/time -l` (macOS) / `tracemalloc` i porównać szczyt RSS przed/po.

## Referencje

- Wzorzec referencyjny A: `src/pbn_integrator/utils/source_scoring_import.py:122`
- Naprawiony przykład A: `src/pbn_integrator/importer/sources.py` `importuj_zrodla`
  (branch `feature/pbn-zrodla-mem`)
- Model i `versions`/`current_version`: `src/pbn_api/models/base.py`
- `pbar`: `src/bpp/util/bpp_specific.py:21`
- Plan wdrożenia: `docs/superpowers/plans/2026-06-04-pbn-import-pamiec.md`
