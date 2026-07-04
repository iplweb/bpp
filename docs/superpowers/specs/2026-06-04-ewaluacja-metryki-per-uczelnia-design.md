# Design — `ewaluacja_metryki` per-uczelnia (wątek D, write+read)

Data: 2026-06-04
Gałąź: `feature/multi-hosted-config`
Kontekst: wątek D z `HANDOFF-multi-hosted.md`. Następny po R2
(`ewaluacja_liczba_n` per-uczelnia). Brief: `NEXT-SESSION-metryki-per-uczelnia.md`.

## Cel i zakres

W instalacji wielouczelnianej **metryki ewaluacyjne autorów liczone i pokazywane
są per uczelnia**. R2 zawęził już *źródło* udziałów per uczelnia (FK `uczelnia`
na `IloscUdzialowDlaAutoraZaRok/ZaCalosc`, cały pipeline `ewaluacja_liczba_n`).
ALE **konsument** w `ewaluacja_metryki` czyta te udziały i pisze
`MetrykaAutora` **globalnie** — więc w multi-install metryki mieszają uczelnie,
a generowanie dla jednej uczelni niszczy metryki pozostałych.

**„Liczba N" w tytule wątku = R2 (zrobione).** `generuj_metryki_task` woła
`oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)` jako krok 1 — to już
per-uczelnia. Wątek D dotyczy **wyłącznie konsumenta-metryki** (krok 2+).

**W zakresie D:**
- FK `uczelnia` na `MetrykaAutora` + `unique_together` z uczelnią + indeks,
- FK `uczelnia` na `StatusGenerowania` (per-uczelnia status generowania;
  koniec globalnego singletonu `pk=1`),
- migracja + backfill (single→domyślna; multi-z-danymi→**wyczyść** regenerowalny
  cache; potem osobna migracja NOT NULL),
- zawężenie pipeline'u liczenia (`utils.py`, `tasks.py`, `oblicz_metryki.py`,
  ścieżka pin/unpin) per uczelnia — w tym naprawa **globalnego destrukcyjnego
  delete** i **knapsack leak** (patrz niżej),
- filtrowanie odczytów (`list`, `detail`, `statistics`, `export`,
  `export_helpers`, `pin_unpin` redirect) po uczelni oglądającego,
- admin: pokaż `uczelnia` (parytet z R2).

**Poza zakresem D:**
- Reguła atrybucji autor→uczelnia z R2 (`aktualna_jednostka.uczelnia` +
  `skupia_pracownikow`) — **nie zmieniamy jej**, tylko **stosujemy**: ścieżka
  bulk dziedziczy uczelnię z wiersza `IloscUdzialow` (który R2 już zatagował tą
  regułą), a ścieżka pin/unpin wyprowadza ją bezpośrednio z
  `autor.aktualna_jednostka.uczelnia` (patrz „Reguła wiodąca”).
- Federacja optymalizacji (`ewaluacja_optymalizacja`) — świadomie odłożona.

## Reguła wiodąca (decyzja usera)

**Metryka jest dla uczelni, na której autor ma udziały.** Jedna metryka na
krotkę `(autor, dyscyplina, uczelnia)`. Autor może (latentnie) mieć metryki na
wielu uczelniach — read-side pokazuje tę dla **uczelni oglądającego** (z
requestu/site, z opcją override superusera).

**Atrybucja (ścieżka bulk) = wiersz źródłowy.** `metryka.uczelnia =
ilosc_udzialow.uczelnia` — wiersz `IloscUdzialowDlaAutoraZaCalosc` jest już
per-uczelnia (R2), więc batch nie zgaduje, tylko dziedziczy. Pole `jednostka` FK
pozostaje jak dziś (`autor.aktualna_jednostka`, display). W ścieżce bulk NIE
re-derywujemy uczelni z `aktualna_jednostka` — bierzemy ją wprost z wiersza.
(Ścieżka pin/unpin nie ma wiersza do dziedziczenia — patrz niżej.)

**Pin/unpin: uczelnia z `aktualna_jednostka`.** Ścieżka pin/unpin nie iteruje
wierszy `IloscUdzialow`, tylko bierze parę `(autor, dyscyplina)` — więc uczelnię
wyprowadza **bezpośrednio z `autor.aktualna_jednostka.uczelnia`** (reguła R2:
`NULL`/jednostka bez `skupia_pracownikow` → autor wykluczony, metryka pomijana).
To ta sama reguła, którą R2 zatagował wiersze `IloscUdzialow`, więc wynik jest
spójny ze ścieżką bulk. Recompute celuje w jedną uczelnię (autor ma jedną
`aktualna_jednostka`); żadnej pętli po uczelniach nie potrzeba.

## Invariant zgodności

Single-install: backfill wpisuje domyślną uczelnię; guard
`tylko_jedna_uczelnia()` short-circuituje filtry read-side (no-op); ścieżka write
operuje na jednej uczelni jak dziś → liczby/metryki **identyczne**. Wszystkie
istniejące testy `ewaluacja_metryki` muszą przejść.

**Jedyna świadoma różnica vs obecny stan (multi-install):** generowanie i odczyty
są zawężone per uczelnia — to cel, nie regresja.

## Zmiany schematu — `src/ewaluacja_metryki/models.py`

### `MetrykaAutora`
- dodać `uczelnia = ForeignKey("bpp.Uczelnia", on_delete=CASCADE, null=True,
  blank=True)` (nullable tylko na czas migracji; docelowo NOT NULL),
- `unique_together` → `("autor", "dyscyplina_naukowa", "uczelnia")`
  (dziś: `("autor", "dyscyplina_naukowa")`),
- dodać `models.Index(fields=["uczelnia", "-srednia_za_slot_nazbierana"])`
  (filtr + ordering listy read-side).

### `StatusGenerowania` (koniec globalnego singletonu)
Dziś singleton wymuszany `self.pk = 1` w `save()` + `get_or_create(pk=1)`.
Per-uczelnia status oznacza **jeden wiersz na uczelnię**:
- dodać `uczelnia = ForeignKey("bpp.Uczelnia", on_delete=CASCADE, null=True,
  blank=True, unique=True)` (docelowo NOT NULL; `unique` = co najwyżej jeden
  status na uczelnię),
- `save()`: usunąć `self.pk = 1` (już nie singleton),
- `get_or_create()` → `get_or_create(uczelnia)`:
  `cls.objects.get_or_create(uczelnia=uczelnia)`,
- wszystkie wołania `StatusGenerowania.get_or_create()` (tasks/views) przekazują
  rozstrzygniętą uczelnię (write: argument taska; read/UI: `uczelnia_dla_odczytu`).

### Migracje (nowe pliki; **NIGDY** nie ruszamy istniejących)
`0006_metrykaautora_uczelnia.py`:
- `AlterUniqueTogether(name='metrykaautora', unique_together=set())`,
- `AddField uczelnia` (nullable),
- `AlterUniqueTogether → {("autor","dyscyplina_naukowa","uczelnia")}`,
- `AddIndex`,
- `RunPython` backfill (`MetrykaAutora` to **regenerowalny cache**):
  `Uczelnia.objects.all()[:2]` — jeśli istnieją wiersze `uczelnia__isnull=True`
  i uczelni jest dokładnie 1 → `update(uczelnia=ta)`; jeśli uczelni ≠ 1 a są
  NULL-e → `MetrykaAutora.objects.all().delete()` (metryki odtworzą się przy
  następnym `generuj_metryki` per-uczelnia — niższe tarcie niż twardy fail,
  bo to cache, nie źródło). Reverse: no-op.

`0007_statusgenerowania_uczelnia.py`:
- `AddField uczelnia` (nullable, `unique=True`),
- `RunPython` backfill: single → istniejący wiersz `pk=1` dostaje domyślną
  uczelnię; multi z NULL-em → `StatusGenerowania.objects.filter(
  uczelnia__isnull=True).delete()` (status to ulotny stan postępu, nie dane).
  Reverse: no-op.

`0008_metrykaautora_statusgenerowania_uczelnia_notnull.py` (po backfillach):
- `AlterField` `MetrykaAutora.uczelnia` → `null=False`,
- `AlterField` `StatusGenerowania.uczelnia` → `null=False`.
  (Osobna migracja `AlterField`, bo NOT NULL może wejść dopiero po wypełnieniu
  wszystkich wierszy backfillem; parytet z 0428 write-side.)

**Numeracja migracji do potwierdzenia przy `makemigrations`** (zależna od
aktualnego stanu zależności `bpp`/`ewaluacja_common`).

## Pipeline liczenia (write) — zawężenie per uczelnia

Trzy luki (wszystkie dziś globalne) do naprawy:

1. **Knapsack leak.** `_calculate_metrics_data` i `oblicz_metryki_dla_autora`
   wołają `autor.zbieraj_sloty(...)` **bez `uczelnia_id`** → `bpp/core.py:22`
   nie filtruje `jednostka__uczelnia_id` → kandydaci z cache WSZYSTKICH uczelni.
   Fix: przekazać `uczelnia_id=<uczelnia metryki>` do obu wywołań `zbieraj_sloty`
   (nazbierane i „wszystko").
2. **Destrukcyjny global delete.** `MetrykaAutora.objects.all().delete()`
   (`utils.py:556` w `generuj_metryki`, `tasks.py:245-246` w
   `generuj_metryki_task_parallel`) → `filter(uczelnia=U).delete()`.
3. **Globalny odczyt źródła.** `IloscUdzialowDlaAutoraZaCalosc.objects.all()`
   (`utils.py:277` w `_get_ilosc_udzialow_queryset`, `tasks.py:231`/`:357`,
   `oblicz_metryki.py:132`) → `filter(uczelnia=U)`.

Atrybucja metryki: tworzenie wiersza zawsze ustawia `metryka.uczelnia` z
**przekazanej** uczelni (parametr funkcji), różny jest tylko jej **źródło**:
- **bulk** (`_process_single_author`, subtask parallel): `ilosc_udzialow.uczelnia`
  — każdy wiersz `IloscUdzialow` ją niesie, więc ścieżka per-wiersz tag-uje
  metrykę i przekazuje `uczelnia_id` do knapsacka bez dodatkowego parametru
  orkiestracji;
- **pin/unpin** (`oblicz_metryki_dla_autora`): uczelnia przekazana przez
  `przelicz_metryki_dla_publikacji` z `autor.aktualna_jednostka.uczelnia`.

Funkcje:
- `generuj_metryki(..., uczelnia)`: nowy param `uczelnia`;
  `_get_ilosc_udzialow_queryset` zawęża po `uczelnia`; delete `nadpisz` →
  `MetrykaAutora.objects.filter(uczelnia=uczelnia).delete()`.
- `_process_single_author` / `_create_or_update_metryka`: tag `uczelnia` z
  `ilosc_udzialow.uczelnia`; `zbieraj_sloty(uczelnia_id=ilosc_udzialow.uczelnia_id)`.
- `oblicz_metryki_dla_autora(autor, dyscyplina, uczelnia, ...)`: agregat
  `IloscUdzialow.filter(autor, dyscyplina, uczelnia)`; `zbieraj_sloty(uczelnia_id=...)`;
  delete/create `filter(... uczelnia=uczelnia)` / `uczelnia=uczelnia`.
- `przelicz_metryki_dla_publikacji(publikacja)`: dla każdej pary
  `(autor, dyscyplina)` wyprowadź uczelnię z `autor.aktualna_jednostka.uczelnia`
  (reguła R2; jednostka `NULL`/bez `skupia_pracownikow` → pomiń autora, brak
  metryki) i wywołaj `oblicz_metryki_dla_autora(autor, dyscyplina, uczelnia)`.
  Jedna uczelnia na autora (jedna `aktualna_jednostka`).

Punkty wejścia — **single-or-fail** (jak B2 `zbieraj_sloty`):
- `generuj_metryki_task` / `generuj_metryki_task_parallel(..., uczelnia_id=None)`:
  `Uczelnia.objects.get(pk=uczelnia_id) if uczelnia_id else Uczelnia.objects.get()`
  (NIGDY `get_default`); scope queryset + delete + przekazanie `uczelnia` do
  `generuj_metryki`; `StatusGenerowania.get_or_create(uczelnia)` (status
  per-uczelnia — krok 4 init i finalizacja celują w wiersz tej uczelni). Krok 1
  (liczba_n) już per-uczelnia. Subtask parallel (`oblicz_metryki_dla_autora_task`)
  czyta uczelnię z wiersza `IloscUdzialow` — bez nowego parametru; delete +
  status init są na poziomie orkiestracji (`generuj_metryki_task_parallel`).
  `finalizuj_generowanie_metryk` musi dostać `uczelnia_id` (chord callback), by
  zamknąć właściwy wiersz statusu.
- CLI `oblicz_metryki`: ma już `--uczelnia-id`; rozszerzyć single-or-fail na
  całość (nie tylko liczbę N); zawęzić `ilosc_udzialow_qs` po uczelni; przekazać
  `uczelnia` do `generuj_metryki`.
- `views/generation.py::UruchomGenerowanieView`: rozstrzygnij uczelnię z requestu
  (`uczelnia_dla_odczytu`) i przekaż `uczelnia_id` do
  `generuj_metryki_task_parallel.delay(...)`; `total_count` z
  `IloscUdzialow.filter(uczelnia=U).count()`; `StatusGenerowania.get_or_create(
  uczelnia=U)` (init `rozpocznij_generowanie` na wierszu tej uczelni). Widoki
  statusu (`StatusGenerowaniaView`, `StatusGenerowaniaPartialView`) też
  rozstrzygają uczelnię z requestu i pokazują jej wiersz.

## Read-side — hybryda `uczelnia_dla_odczytu` (R1), defense-in-depth

Źródło uczelni oglądającego: `raport_slotow.uczelnia_helper.uczelnia_dla_odczytu(request)`
(get_for_request + superuser `?uczelnia=<pk>`). Guard
`bpp.util.uczelnia_scope.tylko_jedna_uczelnia()` → short-circuit single-install
(filtr no-op, zero zmian w zapytaniach gdy 1 uczelnia → invariant).

Wzorzec: widok rozstrzyga uczelnię raz, buduje `base = MetrykaAutora.objects
.filter(uczelnia=U)` (albo niezawężony przy single-install) i z niego korzysta.

- `views/statistics.py`: wszystkie `MetrykaAutora.objects.all()` / agregaty
  (globalne, jednostki, dyscypliny, rozkład wykorzystania, top/bottom) → z
  `base`.
- `views/list.py`: `get_queryset` base po uczelni; listy filtrów
  (`_get_jednostki_wydzialy_context`, `_get_dyscypliny_context`,
  `_get_statistics_context`) po uczelni; `_get_status_context` →
  `StatusGenerowania.get_or_create(uczelnia=U)` (pasek postępu tej uczelni).
- `views/detail.py`: `get_object` zawęża po uczelni (autor z metrykami na >1
  uczelni → pokazujemy tę z otwartej); ranking `_get_position_context` po uczelni.
- `views/export.py`: `ExportListaXLSX` base po uczelni; `ExportStatystykiXLSX`
  rozstrzyga uczelnię, buduje `base_qs` i przekazuje do helperów.
- `export_helpers.py` (**Opcja A**): każdy `export_*` przyjmuje już-zawężony
  `base_qs` z widoku zamiast wewnętrznego `MetrykaAutora.objects.all()`. Helpery
  stają się uczelnia-agnostyczne (czysta prezentacja); decyzja per-uczelnia +
  guard żyją w jednym miejscu (widok). `export_zerowi` (iteracja +
  `Autor_Dyscyplina`) też operuje na `base_qs`.
- `views/pin_unpin.py`: redirect-lookup `MetrykaAutora.filter(autor, dyscyplina)
  .first()` → dodać `uczelnia=U` (jawny filtr, defense-in-depth).

## Admin (drobne, parytet R2)

`MetrykaAutoraAdmin`: `uczelnia` w `list_display`, `list_filter`, oraz w
fieldset „Podstawowe informacje".

## Testy (`fixtures.conftest_multisite`)

- **Invariant single-install:** istniejące testy `ewaluacja_metryki` zielone;
  fixture jednouczelniany → metryki identyczne; guard → filtry no-op.
- **Izolacja multi-install:** 2 uczelnie, autorzy z udziałami w obu (różne
  `IloscUdzialow.uczelnia`); generowanie dla U1 potem U2 → generowanie U2 **NIE**
  wyciera metryk U1 (scoped delete); każda metryka z poprawną `uczelnia`.
- **Knapsack scoping:** metryka liczona dla U1 bierze kandydatów tylko z cache U1
  (`zbieraj_sloty(uczelnia_id=U1)`) — asercja, że praca z jednostki U2 nie wpływa
  na slot/punkty metryki U1.
- **Read defense-in-depth:** list/detail/statistics/export dla U1 nie pokazują
  metryk U2 (asercja pozytywna: moja jest; negatywna: obca nie). Superuser
  `?uczelnia=U2` przełącza widok.
- **Pin/unpin:** recompute dla publikacji zawęża metrykę do uczelni autora
  (`aktualna_jednostka.uczelnia`); autor z jednostki bez `skupia_pracownikow` /
  `NULL` → metryka pomijana; nie tworzy/nie rusza metryk innej uczelni.
- **Status per-uczelnia:** generowanie dla U1 ustawia/odczytuje wiersz
  `StatusGenerowania` U1, nie miesza z postępem U2; `get_or_create(uczelnia=U2)`
  zwraca osobny wiersz. Widok statusu pokazuje pasek właściwej uczelni.
- **Migracja backfill:** single → legacy wiersze dostają domyślną uczelnię (test
  jednostkowy opcjonalny — trudny na świeżej bazie testowej).

## Migracja i deploy

- Single-install: backfill wpisze domyślną uczelnię w legacy `MetrykaAutora` i
  `StatusGenerowania`; następne generowanie przeliczy poprawnie per uczelnia
  (identycznie). NOT NULL wchodzi w `0008` po backfillu.
- Multi-install z danymi: backfill **czyści** legacy `MetrykaAutora`
  (regenerowalny cache → odtworzy się przy najbliższym `generuj_metryki`
  per-uczelnia) oraz usuwa osierocony wiersz `StatusGenerowania` bez uczelni.
  Świadoma różnica vs `0425`/`0009` (te robiły twardy fail) — uzasadniona tym,
  że metryki i status to dane **pochodne/ulotne**, nie źródło prawdy.
- Kolejność deployu: `0006` (FK+backfill metryk) → `0007` (FK+backfill statusu)
  → `0008` (NOT NULL obu). Po deployu uruchomić generowanie per uczelnia.

## Komendy weryfikacji

- Testy: `uv run pytest src/ewaluacja_metryki/ -q -p no:cacheprovider`.
- Guard: `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q`.
- `uv run python src/manage.py makemigrations --check --dry-run`
  (z `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1`).
- Lint: `uv run ruff check <pliki>` ORAZ `uv run ruff format --check <pliki>`
  (NIE `--fix`).

## Dokumenty referencyjne

- Spec R2 (wzorzec): `specs/2026-06-03-ewaluacja-liczba-n-per-uczelnia-design.md`
- Migracja R2 backfill (wzorzec): `ewaluacja_liczba_n/migrations/0009_iloscudzialow_uczelnia.py`
- Write-side sloty (FK+backfill 0425): `specs/2026-06-02-per-uczelnia-sloty-design.md`
- Read-side R1 (helper hybryda): `raport_slotow/uczelnia_helper.py`
- Master: `HANDOFF-multi-hosted.md`; brief: `NEXT-SESSION-metryki-per-uczelnia.md`
