# Deduplikator autorów — tryb ogólny (general)

**Data:** 2026-05-01
**Branch:** `feature/deduplikator-autorow-general`
**Worktree:** `~/Programowanie/bpp-worktrees/deduplikator-autorow-general/`
**Bazowy:** `dev`

## Cel

Rozszerzyć istniejący moduł `src/deduplikator_autorow/` o drugi tryb skanowania, który znajduje duplikaty autorów **niezwiązanych z `OsobaZInstytucji` (PBN)**. Obecny tryb (PBN) iteruje po `OsobaZInstytucji` i obsługuje pracowników instytucji powiązanych z PBN. Nowy tryb (`general`) obsługuje "resztę bazy" — autorów zaimportowanych z PBN jako `Scientist`, ale nie będących pracownikami instytucji, oraz autorów bez powiązania PBN.

Operacyjnie:
1. User uruchamia jeden skan, który robi oba tryby sekwencyjnie.
2. Po skanie: w widoku radio-button-em wybiera, którego trybu wyniki ogląda (PBN / Ogólny / Oba).
3. Dla każdego klastra duplikatów z trybu general — jeżeli **którykolwiek** członek klastra ma `OsobaZInstytucji`, klaster jest pomijany (handluje go tryb PBN).

## Architektura wysokopoziomowa

Rozszerzenie istniejącej aplikacji `deduplikator_autorow`. **Bez nowej aplikacji Django.**

### Pojęcia

- **Tryb skanowania (`scan_mode`)** — pole na `DuplicateScanRun` i `DuplicateCandidate`.
  - `pbn` — kandydat znaleziony przez fazę PBN skanu.
  - `general` — kandydat znaleziony przez fazę general.
  - `both` (tylko na `DuplicateScanRun`) — skan zawiera obie fazy.
- **Pivot (general):** `Autor` z bazy. Klaster jest emitowany tylko jeśli żaden członek nie ma `OsobaZInstytucji`.
- **Wybór "main" w klastrze general** — hierarchia tiebreakerów (patrz sekcja "Wybór głównego").

### Komponenty z reuse (bez zmian lub minimalne)

- `analiza_duplikatow` (scoring) — generalizowany; przyjmuje `(glowny_autor: Autor, kandydat_autor: Autor)` zamiast `osoba_z_instytucji`. Cała logika scoringu (płeć, ORCID, tytuł, imiona, lata, swap) działa po obiektach `Autor`.
- `scal_autora` — bez zmian, działa po `Autor`-ach.
- `LogScalania` — bez zmian.
- `NotADuplicate` (FK→Autor) — bez zmian; działa dla obu trybów.
- Template `duplicate_authors.html` — drobne dodatki: radio mode, badge per-pozycja, pasek statusu fazy.

### Komponenty nowe / zmieniane

- `utils/search_general.py` — nowa strategia generowania kandydatów dla trybu general.
- `utils/main_selection.py` — nowy moduł: hierarchia wyboru głównego w klastrze.
- `utils/cluster.py` — nowy moduł: union-find / connected components nad parami.
- Modele:
  - `IgnoredAuthor` (FK→Scientist) **rename** na `IgnoredScientist`.
  - Nowy `IgnoredAuthor` (FK→Autor) — dla trybu general.
  - `DuplicateScanRun` — nowe pola `scan_mode`, `phase`.
  - `DuplicateCandidate` — nowe pole `scan_mode`; `main_osoba_z_instytucji` zostaje nullable (już jest dziś).
- `tasks.py:scan_for_duplicates` — uruchamia OBA tryby sekwencyjnie pod jednym `DuplicateScanRun`.
- `views.py` — filtr `mode` w GET; rozdzielone akcje dla PBN/general (ignore, reset).
- `utils/export.py` — XLSX z dodatkową kolumną "Tryb".

## Algorytm trybu `general`

### Wejście

`Autor.objects.all()` — pełen zbiór, **bez** wstępnego wyłączania osób z `OsobaZInstytucji` (potrzebne do cluster-skip).

### Krok 1: generowanie par kandydatów

Iteracja po wszystkich `Autor`-ach w kolejności PK rosnącej. Dla każdego pivota:

1. Wywołanie `szukaj_kopii_autora(autor)` — uogólniona wersja `szukaj_kopii`. Heurystyki identyczne jak dziś:
   - exact lastname (case insensitive),
   - reversed compound lastname (`Gal-Cisoń` → `Cisoń-Gal`),
   - compound parts (`Gal-Cisoń` → `Gal`, `Cisoń`),
   - compound member match (`Woźniak` matchuje `Kowalska-Woźniak`),
   - swap imię ↔ nazwisko,
   - dopasowanie imion / inicjałów (`word_match_filter`, `initial_match_filter`).
2. Filtrowanie kandydatów przez `NotADuplicate` i nowy `IgnoredAuthor` (FK→Autor).
3. Dla każdego kandydata: `analiza_duplikatow_pary(pivot, kandydat)` → `confidence_score`, `reasons`.
4. Filtr: `confidence_score >= MIN_CONFIDENCE_TO_STORE` (=50, jak obecnie w PBN).

Wynik kroku 1: zbiór nieuporządkowanych par. **Deduplikacja par symetrycznych** w pamięci (`dict[frozenset({pk_a, pk_b})] -> (score, reasons)`).

### Krok 2: grupowanie w klastry (connected components)

Graf nieskierowany: węzły = `Autor.pk`, krawędzie = pary z kroku 1. Algorytm union-find. Każda spójna komponenta = klaster.

### Krok 3: cluster-skip

Dla każdego klastra:
- Jeżeli **którykolwiek** członek ma `OsobaZInstytucji` (`Autor.pbn_uid.osobazinstytucji` istnieje) → **odrzuć klaster**.
- Inaczej → przekaż do kroku 4.

Statystyki logowane: ile klastrów odrzucono, ile autorów w nich.

### Krok 4: wybór "main" w klastrze (hierarchia B)

Sortowanie członków klastra po kluczu złożonym (kolejne kryteria odpalają tylko przy remisie):

| Priorytet | Kryterium | Kierunek |
|-----------|-----------|----------|
| 1 | `bool(orcid)` | DESC (ma > nie ma) |
| 2 | `bool(pbn_uid)` | DESC (ma > nie ma) |
| 3 | `bool(tytul)` | DESC (ma > nie ma) |
| 4 | `Autor_Dyscyplina.objects.filter(autor=...).exists()` | DESC (ma > nie ma) |
| 5 | `Rekord.objects.prace_autora(autor).count()` | DESC (więcej > mniej) |
| 6 | max rok publikacji (NULL→0) | DESC (nowszy > starszy) |
| 7 | `pk` | ASC (niższy > wyższy) |

Pierwszy w posortowanej liście → `main_autor`. Reszta → `duplicate_autor`-zy.

### Krok 5: emisja `DuplicateCandidate`

Dla klastra `{main, dup1, dup2, ..., dupN}`:
- Dla każdego `dup_i`: zapisujemy `DuplicateCandidate(scan_mode='general', main_autor=main, duplicate_autor=dup_i, confidence_score=score(main, dup_i), reasons=..., priority=calculate_author_priority(dup_i))`.
- Jeżeli para `(main, dup_i)` **nie była** bezpośrednio w grafie (klaster przechodni), wyliczamy score on-the-fly z `analiza_duplikatow_pary(main, dup_i)`.

### Bulk-creation

`DuplicateCandidate` zbierany w pamięci i zapisywany przez `bulk_create(ignore_conflicts=True)` co 1000 sztuk (jak obecny PBN-skan).

### Performance / progress

- Spodziewany czas dla ~50k autorów: kilka–kilkanaście minut w celery (z indeksem na `nazwisko`).
- Progress: `authors_scanned` aktualizowany co `PROGRESS_UPDATE_INTERVAL=100` w fazie general (jak dziś dla PBN).
- W ramach jednego `DuplicateScanRun`: total = `OsobaZInstytucji.count()` + `Autor.count()` (suma obu faz).

## Zmiany modelu i migracje

**Kolejność wykonania migracji jest istotna:**
1. Migracja 1 (rename `IgnoredAuthor` → `IgnoredScientist`) — **musi** wykonać się przed Migracja 2, bo Migracja 2 tworzy nową klasę `IgnoredAuthor` która zajmie zwolnioną nazwę tabeli/modelu.
2. Migracja 2 (nowy `IgnoredAuthor` FK→Autor).
3. Migracja 3 (pola `scan_mode`, `phase`, indexes, constraint replace).
4. Migracja 4 (backfill — opcjonalnie razem z Migracja 3 jeśli `default='pbn'` na `AddField` wystarczy).

### Migracja 1: rename `IgnoredAuthor` → `IgnoredScientist`

```python
operations = [
    migrations.RenameModel(old_name="IgnoredAuthor", new_name="IgnoredScientist"),
    migrations.AlterModelOptions(
        name="ignoredscientist",
        options={
            "verbose_name": "Ignorowany Scientist (PBN)",
            "verbose_name_plural": "Ignorowani Scientist (PBN)",
            "ordering": ["-created_on"],
        },
    ),
]
```

Wszystkie referencje w `tasks.py`, `views.py`, `finders.py`, `admin.py`, templates → `IgnoredAuthor` → `IgnoredScientist`.

### Migracja 2: nowy `IgnoredAuthor` (FK→Autor)

```python
class IgnoredAuthor(models.Model):
    autor = models.OneToOneField(
        "bpp.Autor", on_delete=models.CASCADE, db_index=True,
        verbose_name="Autor (BPP)",
    )
    reason = models.CharField(max_length=500, blank=True)
    created_on = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(BppUser, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Ignorowany autor (BPP)"
        verbose_name_plural = "Ignorowani autorzy (BPP)"
        ordering = ["-created_on"]
```

### Migracja 3: pole `scan_mode` na `DuplicateScanRun` i `DuplicateCandidate`

Na `DuplicateScanRun`:

```python
scan_mode = models.CharField(
    "Tryb skanowania", max_length=20,
    choices=[("pbn", "PBN"), ("general", "Ogólny"), ("both", "Oba")],
    default="both", db_index=True,
)
phase = models.CharField(
    "Aktualna faza", max_length=20, blank=True,
    choices=[("pbn", "Faza PBN"), ("general", "Faza ogólna")],
)
```

Na `DuplicateCandidate`:

```python
scan_mode = models.CharField(
    "Tryb", max_length=20,
    choices=[("pbn", "PBN"), ("general", "Ogólny")],
    default="pbn", db_index=True,
)

class Meta:
    indexes = [
        ...,
        models.Index(fields=["scan_run", "scan_mode", "status"]),
    ]
    constraints = [
        # Replace existing unique_scan_main_duplicate
        models.UniqueConstraint(
            fields=["scan_run", "scan_mode", "main_autor", "duplicate_autor"],
            name="unique_scan_mode_main_duplicate",
        ),
    ]
```

`UniqueConstraint` z `scan_mode` zastępuje istniejący `unique_scan_main_duplicate` — para autorów może (defensywnie) wystąpić w obu trybach, ale nie dwa razy w tym samym trybie/skanie.

### Migracja 4: backfill `scan_mode` na istniejących `DuplicateCandidate`

`RunPython` ustawia `scan_mode='pbn'` na wszystkich istniejących wierszach (wszystkie dotychczasowe wpisy pochodzą z trybu PBN). Wykonuje się **przed** `Migracja 3 part B` w której zmieniany jest `default` z `pbn` → standalone constraint, lub jako jedna sekwencja: `AddField(default='pbn')` → `RunPython(no-op)` (default już sam wypełnia).

## Celery task: `scan_for_duplicates`

Jeden task, dwie fazy. Sygnatura zostaje (`user_id`, `min_confidence`).

```python
@shared_task(bind=True, name="deduplikator_autorow.scan_for_duplicates")
def scan_for_duplicates(self, user_id=None, min_confidence=MIN_CONFIDENCE_TO_STORE):
    scan_run = DuplicateScanRun.objects.create(
        scan_mode="both",
        status=DuplicateScanRun.Status.RUNNING,
        ...
    )

    # FAZA 1: PBN
    scan_run.phase = "pbn"
    scan_run.save(update_fields=["phase"])
    _run_pbn_phase(scan_run, min_confidence)
    if scan_run.status == CANCELLED: return ...

    # FAZA 2: general
    scan_run.phase = "general"
    scan_run.save(update_fields=["phase"])
    _run_general_phase(scan_run, min_confidence)
    if scan_run.status == CANCELLED: return ...

    scan_run.status = COMPLETED
    scan_run.finished_at = timezone.now()
    scan_run.save()
```

`_run_pbn_phase` — istniejąca logika (wycinamy z obecnego body taska do funkcji prywatnej). Każdy emitowany kandydat ma `scan_mode='pbn'`.

`_run_general_phase` — nowa funkcja realizująca algorytm z sekcji "Algorytm trybu general". Każdy emitowany kandydat ma `scan_mode='general'`.

Total progress = sum obu faz (`total_authors_to_scan = osoby_pbn.count() + autor.count()`). `authors_scanned` rośnie monotonicznie przez obie fazy.

## UI / widoki

### Template `duplicate_authors.html`

1. **Górny panel statusu skanu:**
   - Jeden przycisk `Skanuj duplikaty` (uruchamia jeden task; oba tryby).
   - Pasek postępu: "Faza X z 2: PBN/Ogólny — Y%" + ogólny progress 0–100%.
   - ETA jak dziś.

2. **Selector trybu (radio inline):**

   ```
   Pokaż wyniki: ( ) PBN  ( ) Ogólny  (•) Oba
   ```

   GET param: `?mode=pbn|general|both`. Domyślnie `both`.

3. **Lista pending-candidates** — filtrowana wg `mode`. Każdy nagłówek/grupa ma badge:
   - `[PBN]` (np. niebieski),
   - `[OGÓLNY]` (np. zielony/pomarańczowy).

4. **Counters:**

   ```
   PBN: 123 par do sprawdzenia
   Ogólny: 45 par do sprawdzenia
   ```

5. **Pobierz XLSX** — pojedynczy przycisk. Plik zawiera **wszystkie** pending-candidates (oba tryby), z dodatkową kolumną `Tryb`.

### `views.py`

- `duplicate_authors_view(request)`:
  - Czyta `mode` z GET (`pbn`/`general`/`both`, default `both`).
  - Pobiera pending z `DuplicateCandidate.objects.filter(scan_run=latest_completed, status=PENDING)`. Jeśli `mode != 'both'` → `.filter(scan_mode=mode)`.
  - `_get_next_candidate_group(scan_run, skip_count, mode)` — dokłada `scan_mode=mode` jeśli ≠ `both`.
  - Główny autor pivota to zawsze `Autor`. W trybie general `glowny_autor.pbn_uid` może być `None` — template chroniony przez `{% if scientist %}` (już jest).

- `scal_autorow_view`:
  - **Zmiana parametrów:** wprowadzamy `main_autor_id` / `duplicate_autor_id` (PK Autor-a).
  - Backwards-compat: jeżeli przyszły stare parametry `main_scientist_id` / `duplicate_scientist_id` (z dotychczasowego frontu PBN) — view tłumaczy je przez `Scientist.rekord_w_bpp.pk` na Autor PK i działa dalej.
  - Frontend (template) **zawsze przekazuje nowe parametry** (Autor PK) — nie ma w nim żadnego rozróżnienia po trybie. W trybie PBN main_autor_id to po prostu `glowny_autor.pk`, niezależnie od tego, czy ma Scientist.

- `ignore_author` rozdzielamy:
  - `ignore_scientist(request)` (POST `scientist_id`) → `IgnoredScientist`.
  - `ignore_autor(request)` (POST `autor_id`) → `IgnoredAuthor`.
  - W template przycisk "Ignoruj autora" wybiera odpowiednią akcję na podstawie trybu.

- `reset_ignored_authors` rozdzielamy:
  - `reset_ignored_scientists` → kasuje `IgnoredScientist`.
  - `reset_ignored_autorzy` → kasuje `IgnoredAuthor`.

### `urls.py`

Zmiany:
- Istniejący path `ignore-author/` zmienia name z `ignore_author` na `ignore_scientist` (URL i nazwa w `name=` razem) — view bierze `scientist_id` jak dziś, zapisuje do `IgnoredScientist`. To wewnętrzny endpoint AJAX widoku `duplicate_authors`, brak zewnętrznych konsumentów do zachowania.
- Istniejący path `reset-ignored-authors/` zmienia name na `reset_ignored_scientists`.
- Nowe paths:
  - `ignore-autor/` (name `ignore_autor`) → `views.ignore_autor` (POST `autor_id` → `IgnoredAuthor`).
  - `reset-ignored-autorzy/` (name `reset_ignored_autorzy`) → kasuje wszystkie `IgnoredAuthor`.

### `utils/export.py`

`export_duplicates_to_xlsx()`:
- Pobiera **wszystkie** pending z najnowszego completed scan run (oba tryby).
- Dodaje kolumnę "Tryb" (PBN/Ogólny).
- Pozostałe kolumny bez zmian (główny autor, PBN UID głównego — może być pusty w general — duplikat, PBN UID duplikatu, liczba publikacji, lata).

## Edge cases

1. **Kandydat w obu trybach naraz** — nie powinno się zdarzyć (general odrzuca klastry z OsobaZInstytucji), ale defensywnie unique constraint zostaje rozszerzony o `scan_mode` (patrz Migracja 3). Para `(main, dup)` może wystąpić w obu trybach, ale tylko raz w każdym.

2. **Jeden autor w wielu klastrach** — możliwe gdy heurystyka przechodnia jest słaba (A∈klaster1 jako main z B, A∈klaster2 jako dup C). UI grupuje po `main_autor`, więc A pojawi się w dwóch grupach. Akceptowane w pierwszej iteracji; warning w logu skanu.

3. **Pivot bez `nazwisko`** — pomijamy w pętli (jak dziś).

4. **Pre-flight check świeżości danych PBN** — blokuje cały skan (oba tryby), bo faza PBN jej wymaga. Komunikat: "Pobierz świeże dane PBN, aby uruchomić skanowanie."

5. **Anulowanie skanu między fazami** — `scan_run.status == CANCELLED` sprawdzane na początku każdej iteracji w obu fazach. Po fazie PBN → przed fazą general — sprawdzenie ponownie.

6. **Główny autor po general jest do scalenia, ale ma wpis `NotADuplicate`** — `szukaj_kopii_autora` filtruje przez `NotADuplicate` (jak dziś `szukaj_kopii` w PBN).

7. **Kasowanie wszystkich `DuplicateCandidate` na początku skanu** — bez zmian; usuwamy wszystkich pending z poprzedniego skanu (replace mode), bo nowy skan jest źródłem prawdy.

## Testy

Lokalizacja: `src/deduplikator_autorow/tests/`.

### `test_general_scan.py` — algorytm general

- `test_general_finds_simple_pair` — dwóch `Kowalski Jan` (różne PK), żaden bez OsobaZInstytucji → 1 para.
- `test_general_skips_cluster_with_osobaz_instytucji` — klaster {A, B, C}, B ma OsobaZInstytucji → klaster pominięty.
- `test_general_main_selection_hierarchy` — różne kombinacje ORCID/pbn_uid/tytuł/dyscyplina/pubs/PK → main wybierany zgodnie z hierarchią B.
- `test_general_main_pk_tiebreaker` — wszystko równe → niższy PK wygrywa.
- `test_general_swap_detection` — `Jan Kowalski` ↔ `Kowalski Jan` → para znaleziona.
- `test_general_compound_lastname` — `Gal-Cisoń` matchuje `Cisoń-Gal`.
- `test_general_pair_dedup` — para (A,B) i (B,A) emitowane raz.
- `test_general_transitive_cluster` — A~B i B~C, ale A≁C → klaster {A,B,C} z trzema parami pod jednym main.
- `test_general_respects_not_a_duplicate` — autor w `NotADuplicate` nie pojawia się jako kandydat.
- `test_general_respects_ignored_author` — autor w `IgnoredAuthor` nie pojawia się ani jako pivot, ani jako kandydat.

### `test_models.py` — modele

- `test_ignored_scientist_rename_works` — `IgnoredScientist` zapisuje się i odczytuje.
- `test_ignored_author_creates_for_autor` — `IgnoredAuthor(autor=...)` zapisuje się.
- `test_duplicate_candidate_scan_mode_default_pbn` — domyślnie `pbn`.
- `test_duplicate_candidate_scan_mode_general` — `general` zapisywane.
- `test_duplicate_scan_run_phase_field` — `phase` zapisywane.

### `test_tasks.py` — celery task

- `test_scan_runs_pbn_then_general_phase` — z fixturem `OsobaZInstytucji` i autorami spoza, weryfikuje że oba fazy emitują kandydaty z odpowiednimi `scan_mode`.
- `test_scan_progress_total_is_sum_of_phases` — `total_authors_to_scan == osoby.count() + autor.count()`.
- `test_scan_progress_reaches_100_after_both_phases` — po sukcesie, `progress_percent == 100`.
- `test_scan_cancellation_during_pbn_phase` — anulowanie w fazie 1 → status `CANCELLED`, faza 2 nie startuje.
- `test_scan_cancellation_during_general_phase` — anulowanie w fazie 2 → status `CANCELLED`.
- `test_scan_skips_clusters_with_osoba_instytucji` — w fixture'ze klaster z `OsobaZInstytucji` nie ląduje w `DuplicateCandidate(scan_mode='general')`.

### `test_views.py` — widoki

- `test_view_filter_by_mode_pbn` — `?mode=pbn` pokazuje tylko PBN.
- `test_view_filter_by_mode_general` — `?mode=general` tylko general.
- `test_view_filter_by_mode_both` — `?mode=both` (default) pokazuje oba.
- `test_view_general_mode_main_without_scientist` — render działa kiedy `glowny_autor.pbn_uid is None`.
- `test_xlsx_export_includes_mode_column` — generuje XLSX z kolumną "Tryb".
- `test_ignore_autor_endpoint` — POST do `ignore_autor` zapisuje `IgnoredAuthor`.
- `test_ignore_scientist_endpoint` — POST do `ignore_scientist` zapisuje `IgnoredScientist`.
- `test_scal_autorow_uses_autor_ids` — nowe parametry `main_autor_id` / `duplicate_autor_id` działają.
- `test_scal_autorow_backwards_compat_scientist_ids` — stare parametry dalej działają.
- `test_counters_split_by_mode` — counters pokazują osobne liczby dla PBN i general.

### Backwards-compat

Istniejące testy PBN (jeżeli są w repo) muszą dalej przechodzić bez modyfikacji logiki.

## Deliverables

- Zaktualizowane pliki w `src/deduplikator_autorow/`:
  - nowy `utils/search_general.py`,
  - nowy `utils/main_selection.py`,
  - nowy `utils/cluster.py`,
  - zaktualizowany `tasks.py`, `views.py`, `urls.py`, `models.py`, `admin.py`, `utils/export.py`,
  - zaktualizowany template `templates/deduplikator_autorow/duplicate_authors.html`.
- 4 migracje (rename, new model, scan_mode fields + indexes, backfill).
- Testy w `src/deduplikator_autorow/tests/`.
- Newsfragment towncrier (`feat`).

## Co celowo poza zakresem

- Refactor heurystyki `szukaj_kopii` do nowych typów dopasowań (np. trigram similarity).
- Detekcja duplikatów na bazie publikacji (np. wspólna tematyka, wspólne afiliacje).
- Asynchroniczne odpalanie obu faz równolegle (sekwencyjnie wystarcza).
- Auto-merge wysokiej-pewności klastrów (zostaje manualne).
