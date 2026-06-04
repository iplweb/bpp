# Design — per-uczelnia sloty: READ-SIDE (R1)

Data: 2026-06-03
Gałąź: `feature/multi-hosted-config`
Poprzednik: write-side (`2026-06-02-per-uczelnia-sloty-design.md`) — KOMPLETNY.
Discovery: `HANDOFF-multi-hosted.md` §A; self-review write-side:
`docs/superpowers/reviews/2026-06-03-self-review-per-uczelnia-sloty-write-side.md`.

## Cel i zakres

Write-side zapisuje cache slotów per (rekord, uczelnia). **Dopóki ODCZYTY nie
filtrują po uczelni oglądającego, instalacja wielouczelniana liczy/pokazuje
międzyuczelniano.** R1 wprowadza filtrowanie odczytów slotowych po uczelni.

**W zakresie R1:**
- kolumna `uczelnia` w widoku `bpp_cache_punktacja_autora_view` + pole na modelu,
- helper rozstrzygający uczelnię oglądającego (hybryda: site + override superusera),
- `raport_slotow`: `RaportSlotowUczelnia` (FK uczelnia + generacja zawężona),
  `RaportSlotowAutor`, raport „zerowy", pipeline temp-tabel,
- proste filtry read-only: `ewaluacja_metryki` (`utils.py`, `views/detail.py`,
  `views/list.py`), `oswiadczenia/views.py`, `ewaluacja_common/utils.py`,
  `bpp/core.py` (`zbieraj_sloty`), komenda `zbieraj_sloty`,
- API `api_v1/.../raport_slotow_uczelnia` (jedzie na `RaportSlotowUczelnia`),
- hardening z self-review: indeks `(rekord_id, uczelnia, dyscyplina)` (#2),
  udokumentowanie asymetrii `skupia_pracownikow` (#3).

**Poza zakresem R1 (osobne wątki):**
- **R2 — `ewaluacja_liczba_n` per-uczelnia** (write+read, schemat `IloscUdzialow*`),
- **Federacja optymalizacji** (`ewaluacja_optymalizacja`,
  `ewaluacja_optymalizuj_publikacje`) — **świadomie ODŁOŻONA, nie teraz**,
- integrator (handoff §D), drobne (§E), NOT NULL na `Cache_Punktacja_Dyscypliny.uczelnia` (#5).

**OUT (discovery 2026-06-03):** `ewaluacja2021` (apka WYGASZANA — husk; brak URL-i,
brak komend, odsprzęgnięta); rankingi (nie czytają cache); `ewaluacja_liczba_n`
NIE czyta `Cache_Punktacja` (ma własny wymiar — R2).

## Decyzje (od usera)

1. **Źródło „uczelni oglądającego" — HYBRYDA.** Domyślnie `get_for_request(request)`
   (każda uczelnia = osobny site/domena, user widzi swoją). Superuser może
   nadpisać jawnym wyborem uczelni (param). Reszta runtime woła jeden helper.
2. **Filtr na poziomie widoku — KOLUMNA `uczelnia` w widoku** (nie rozproszony
   `jednostka__uczelnia`). Czyste, wydajne (indeks), jednolite z
   `Cache_Punktacja_Dyscypliny.uczelnia`.

## Invariant zgodności

Przy DOKŁADNIE jednej uczelni filtr `uczelnia=U` / `jednostka__uczelnia=U` jest
no-opem (wszystkie jednostki wskazują tę jedną uczelnię — `Jednostka.uczelnia`
NOT NULL). Raporty, eksporty, „autorzy zerowi", API → identyczne jak dziś.

## Komponenty

### 1. Widok `Cache_Punktacja_Autora_Query_View` + kolumna `uczelnia`
Stan: widok (migracja 0425, strict join po uczelni) NIE eksponuje `uczelnia`;
model `managed=False` też nie ma pola.
- Nowa migracja DROP+CREATE widoku: dodać `j.uczelnia_id` do SELECT (join `j`
  do `bpp_jednostka` już jest).
- Model `Cache_Punktacja_Autora_Query_View`: dodać
  `uczelnia = ForeignKey("bpp.Uczelnia", DO_NOTHING)`.
- Dzięki temu konsumenci filtrują `.filter(uczelnia=U)` bez joinu.
- `reverse_sql` przywraca wariant bez kolumny (z 0425).
> Reguła projektu: NOWY plik migracji (nie edytuj istniejących). 0425 zostaje
> jak jest (strict join + backfill).

### 2. Helper rozstrzygania uczelni oglądającego
Nowy, jedno miejsce (np. `bpp/multidyscyplinarnosc`/`uczelnia` utils albo
`raport_slotow`/wspólny): `uczelnia_dla_odczytu(request)`:
- bazowo `Uczelnia.objects.get_for_request(request)`,
- jeśli `request.user.is_superuser` i podano jawny param (`?uczelnia=<pk>`/pole
  formularza) → ta uczelnia,
- zwraca obiekt `Uczelnia` (lub `None` → zachowanie jak dziś tylko w single-edge).
Wszyscy konsumenci read-side wołają ten helper — hybryda w jednym punkcie.

### 3. `raport_slotow` (główny konsument)
- **`RaportSlotowUczelnia`** (`models/uczelnia.py`, `long_running.Report`,
  generacja w tle BEZ requestu): dodać FK `uczelnia` (nullable; migracja +
  backfill single→domyślna, multi→stare raporty to artefakty historyczne, zostają;
  nowe ZAWSZE ustawiają uczelnię z helpera przy zamówieniu). Generacja (pipeline
  temp-tabel) filtruje feeding-queryset po `self.uczelnia`.
- **`zbieraj_sloty`** (`bpp/core.py`, czyta `Cache_Punktacja_Autora_Query`):
  dodać `uczelnia_id=None` → `filter(jednostka__uczelnia_id=uczelnia_id)` gdy podane.
  Wołane przez generację raportu (z `self.uczelnia`) i przez komendę
  `zbieraj_sloty` (uczelnia z argumentu / `.get()` single-or-fail).
- **Raport „zerowy"** (`views/zerowy.py` → `create_temporary_table_as(...)`,
  `core.autorzy_zerowi`/`autorzy_z_punktami` z `Cache_Punktacja_Autora_Query_View`):
  queryset źródłowy filtruje `uczelnia=U`. Temp-tabele są session-scoped
  (`CREATE TEMPORARY`), brak kolizji między uczelniami — wystarczy zawęzić źródło.
- **`RaportSlotowAutor`** (`views/autor.py`, czyta `..._Query_View`): filtr
  `uczelnia = uczelnia_dla_odczytu(request)`.
- **`filters.py`/`tables.py`** (`Cache_Punktacja_Autora_Sum_Group`): zapełniane
  z zawężonego źródła; filtr w pipeline, nie w tabeli prezentacyjnej.

### 4. Proste filtry read-only
Dodać `.filter(uczelnia=U)` / `.filter(jednostka__uczelnia=U)` (`U` z helpera;
komenda → argument/`.get()`):
- `ewaluacja_metryki`: `utils.py`, `views/detail.py`, `views/list.py`,
- `oswiadczenia/views.py`,
- `ewaluacja_common/utils.py`,
- `bpp/core.py` (przez `zbieraj_sloty`), `bpp/management/commands/zbieraj_sloty.py`.

### 5. API
`api_v1/.../raport_slotow_uczelnia` (viewset+serializer) — opiera się na
`RaportSlotowUczelnia`; po pkt 3 dziedziczy uczelnię z Report. Sprawdzić, czy
queryset viewsetu sam nie listuje cudzych raportów → ograniczyć do uczelni
żądającego (hybryda).

> **Realizacja (2026-06-04, Audyt 4b):** viewset filtruje per-OWNER
> (`request.user`), nie per-UCZELNIA. Bezpieczne — user nie zobaczy cudzego
> raportu. Dla R1 przyjmujemy **ownership ≈ uczelnia** (świadoma decyzja). Edge
> nieobsłużony: superuser z override `?uczelnia=` widzi przez API własne raporty
> WSZYSTKICH uczelni naraz (mała populacja, akceptowalne dla R1). Pełny per-uczelnia
> filtr API — ewentualny późniejszy follow-up.

## Data flow

request → `uczelnia_dla_odczytu(request)` (site lub override superusera) →
filtr `uczelnia=U` na widoku/Query → (raport) zawężony queryset feeduje
session-scoped temp-tabele → tabela django_tables2 / eksport XLSX/PDF / API.
Komendy/tło: uczelnia z FK Report-u lub argumentu, nie z requestu.

## Migracje
- M1 (bpp): DROP+CREATE widoku z kolumną `uczelnia_id` + model field. Nowy plik.
- M2 (bpp): indeks `(rekord_id, uczelnia, dyscyplina)` na
  `Cache_Punktacja_Dyscypliny` (hardening #2).
- M3 (raport_slotow): FK `uczelnia` na `RaportSlotowUczelnia` (nullable) +
  RunPython backfill (single→domyślna; multi→stare raporty zostają null).
- Reguła: tylko nowe pliki; istniejących nie edytujemy.

## Testy
- Invariant single-install: raport uczelnia/autor/zerowy + eksport → liczby
  identyczne z obecnymi (fixture jednouczelniany; ochrona regresji).
- Multi-install: 2 uczelnie, rekord współautorski → raport uczelni A widzi tylko
  autorów A (i ich sloty z partycji A), raport B tylko B; brak przecieku.
- Widok: kolumna `uczelnia` = `jednostka.uczelnia` dla każdego wiersza.
- Helper: zwykły user → site; superuser + param → wybrana; non-super + param →
  ignorowany (bezpieczeństwo, brak podglądu cudzej uczelni).
- Raport „zerowy" multi-install: autorzy zerowi liczeni w obrębie uczelni.
- Komenda `zbieraj_sloty` bez uczelni w single → OK; w multi bez argumentu →
  jawny błąd (`.get()` single-or-fail).
- API: user uczelni A nie listuje raportów uczelni B.

## Hardening wpięty (z self-review)
- **#2** indeks `(rekord_id, uczelnia, dyscyplina)` (M2).
- **#3** asymetria `skupia_pracownikow` (`_zapisz` filtruje, `autorzy_z_dyscypliny`
  nie) — udokumentować w kodzie/komentarzu przy konsumentach widoku, by czytający
  wiedział, że CPD `autorzy_z_dyscypliny` może zawierać PK bez wiersza CPA.

## Co jeszcze do PRAWDZIWEJ wielouczelnianości (po R1)
Lista świadomie utrzymywana — stan „ile zostało do pełnej multi-uczelnianości":
1. **R2 — `ewaluacja_liczba_n` per-uczelnia (write+read).** Modele udziałów autora
   `IloscUdzialowDlaAutoraZaRok`/`...ZaCalosc` NIE mają `uczelnia` → dodać FK +
   migracja/backfill + poprawić `unique_together` + zawęzić liczenie udziałów
   per uczelnia. (`LiczbaNDlaUczelni`, `DyscyplinaNieRaportowana`, widoki,
   komenda `przelicz_n` — już per-uczelnia.)
2. **Federacja optymalizacji — ODŁOŻONA (nie teraz, decyzja usera).**
   `ewaluacja_optymalizacja` (`core/*`, `tasks/unpinning/*`, `views/*`) +
   `ewaluacja_optymalizuj_publikacje` muszą maksymalizować wynik w obrębie CAŁEJ
   federacji uczelni, nie pojedynczej — inny problem niż filtr per-uczelnia.
3. **Hardening #1 — `_dopasuj_kalkulator` liczy `wiele_hst`/próg globalnie**
   (wszystkie uczelnie), kalkulator używany per-uczelnia → rekord cross-uczelnia
   mieszający HST/nie-HST dziedziczy globalne `wiele_hst`. Test + decyzja w F.
4. **NOT NULL na `Cache_Punktacja_Dyscypliny.uczelnia`** (#5) — po uporządkowaniu
   fixtures tworzących NULL w runtime.
5. **Integrator per-uczelnia** (handoff §D): matcher PBN/afiliacje na `objects.default`.
6. **Drobne** (handoff §E): usunięcie `get_default` z `adapters/wydawnictwo.py`.

## Komendy weryfikacji
- Testy: `uv run pytest src/raport_slotow/ src/ewaluacja_metryki/ src/oswiadczenia/ src/bpp/tests/test_models/test_sloty/ -q -p no:cacheprovider`.
- `uv run python src/manage.py makemigrations --check --dry-run`
  (z `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1`).
- Lint: `uv run ruff check <pliki>` (NIE `--fix`).
