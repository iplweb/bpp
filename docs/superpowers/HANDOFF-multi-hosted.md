# HANDOFF — praca multi-hosted (stan na 2026-06-03)

Notatka do wznowienia po reset/compact sesji. Gałąź: `feature/multi-hosted-config`.
Stan git: lokalny HEAD `c2bfb2c60`; origin = `18d0cd1d1` (1 commit lokalny
niewypushowany — fix migracji 0425, patrz niżej).

Kontekst projektu: BPP (Django), instalacja **wielouczelniana** — jedna instancja
obsługuje wiele obiektów `Uczelnia`, każda z własną konfiguracją (PBN tokeny,
flagi wyświetlania itd.). Cel całości: żaden runtime nie „zgaduje" uczelni
(`get_default()` = pierwsza-z-brzegu), tylko używa właściwej; a liczby
(sloty/punktacja/raporty) są liczone i pokazywane **per uczelnia**.

---

## CO ZROBIONE (3 duże wątki)

### Wątek 1: rozbicie `PBNClient` na dwie warstwy (Wariant B) — KOMPLETNY
Spec: `docs/superpowers/specs/2026-06-02-pbn-client-split-design.md`

- **`src/pbn_client/`** — czysta, reusable warstwa protokołu PBN (transport,
  auth, pagination, mixiny słownikowo-CRUD, `StatementsMixin`, `PBNClient`).
  **Zero importów `bpp`/`pbn_api`** (zweryfikowane). Kandydat na osobny pakiet.
- **`BppPBNClient`** w `pbn_api/client/__init__.py` — dziedziczy po `PBNClient`,
  dokłada orchestrację (`publication_sync`, `disciplines`) i **zna swoją
  `Uczelnia`** (`__init__(transport, uczelnia)`). `get_default()` zniknął z
  `publication_sync` i z głównej ścieżki adaptera.
- Fabryki: `Uczelnia.pbn_client()`, `PBNBaseCommand.get_client()`, fixtura
  `pbn_client`. `pbn_api.client` to shim (kompatybilność wsteczna, 35 importów).
- Test: `src/pbn_api/tests/test_multihosted.py`.

### Wątek 2: cleanup `get_default` (Fazy 1–9) — KOMPLETNY
Plan: `docs/superpowers/plans/2026-06-02-get-default-cleanup.md`
Audyt + status: `docs/deweloper/audyt-multihosted-pbn.md`

Reguła binarna: runtime z dostępną uczelnią → **jawna uczelnia**
(`get_for_request` / argument / FK / `self.uczelnia`); reszta akceptowalna →
`Uczelnia.objects.get()` (single-or-fail).
- **Faza 9 = guard:** `src/bpp/tests/test_multihosted_get_default_guard.py`
  zamraża whitelistę świadomych miejsc; nowy `get_default` w runtime → fail CI.

### Wątek 3: per-uczelnia liczenie slotów/punktacji — WRITE-SIDE KOMPLETNY
Spec: `docs/superpowers/specs/2026-06-02-per-uczelnia-sloty-design.md`
Plan: `docs/superpowers/plans/2026-06-02-per-uczelnia-sloty.md` (Taski 1–9 ✓)
Self-review: `docs/superpowers/reviews/2026-06-03-self-review-per-uczelnia-sloty-write-side.md`

**Reguła wiodąca (decyzja usera):** *true per-university partition* — dla pracy
współautorskiej między uczelniami dzielnik `k` (autorzy z dyscypliny) i `m`
(wszyscy autorzy) zawężony do autorów DANEJ uczelni. Zmienia liczby dla prac
cross-uczelnia (caveat regulacyjny MEiN odnotowany w spec). Invariant: przy
DOKŁADNIE jednej uczelni liczby identyczne jak dawniej.

Zrobione (commity `9848dca8f`…`d961b2cb4` + `c74e4aba5` + `c2bfb2c60`):
- `Cache_Punktacja_Dyscypliny` ma FK `uczelnia` (nullable) + serialize + indeks.
- `SlotMixin._autorzy_qs()` filtruje autorów po `jednostka__uczelnia`; `wszyscy`,
  `autorzy_z_dyscypliny`, `dyscypliny`, `liczba_k`, `k_przez_m` przez ten szew.
- `ISlot(original, uczelnia=None)` + `_rozstrzygnij_uczelnie` (single→ta jedna;
  1 uczelnia rekordu→ona; >1→`CannotAdapt`) + `_dopasuj_kalkulator` (selekcja
  progu, uczelnia-niezależna). Usunięty wewnętrzny `get_default`.
- `IPunktacjaCacher(original)` (bez param. uczelni): `removeEntries` kasuje cały
  rekord; `rebuildEntries` pętli po `_uczelnie_do_przeliczenia` (fast-track
  `count()==1`) z `ISlot(..., uczelnia=U)`; `_zapisz` taguje wiersze uczelnią;
  `serialize` deterministyczny.
- `uczelnie_rekordu()` na `ModelZPrzeliczaniemDyscyplin`;
  `przelicz_punkty_dyscyplin()` bez parametru, bez `get_default`.
- **Migracja 0425 (fix `c2bfb2c60`):** `RunPython backfill` — 1 uczelnia → wpisz
  jej ID w legacy `Cache_Punktacja_Dyscypliny.uczelnia_id IS NULL`; >1 z NULL-ami
  → `raise` (głośny fail, dzielnik per-uczelnia nie do zgadnięcia); świeża baza →
  no-op. Widok `bpp_cache_punktacja_autora_view` = **strict** join po uczelni
  (bez `IS NULL`; band-aid usunięty). Fixture `raport_slotow` ustawia uczelnię.

**Self-review (3 niezależne źródła):** partycja dzielnika szczelna; invariant
single-install trzyma (load-bearing: `Jednostka.uczelnia` jest NOT NULL → filtr
no-op przy jednej uczelni); brak bugów CRITICAL/HIGH. Backlog hardeningu niżej.

---

## CO ZOSTAŁO

### A) NASTĘPNY DUŻY WĄTEK: read-side (filtrowanie odczytów po uczelni)  ← spec tutaj
Po write-side cache trzyma wiersze per (rekord, uczelnia). Dopóki **odczyty** nie
filtrują po uczelni oglądającego, multi-install liczyłby międzyuczelniano.
**Single-install bezpieczny** (jeden komplet wierszy), więc read-side to osobny spec.
Kontrakt: filtrować po uczelni oglądającego (`get_for_request`) — `Cache_Punktacja_Autora`
po `jednostka__uczelnia`, `Cache_Punktacja_Dyscypliny` po `uczelnia`.

Zinwentaryzowani konsumenci (z adnotacjami usera w spec) — STATUSY DO ROZSTRZYGNIĘCIA
w Kroku „discovery" przed spec:
1. **raport_slotow** (`core.py`, `tables.py`, `filters.py`, `views/autor.py`,
   `models/uczelnia.py`) — ISTOTNE, główny konsument widoku + tabel
   `_Sum`/`_Sum_Group`. Czysty filtr per-uczelnia. **Priorytet.**
2. Widok `Cache_Punktacja_Autora_Query_View` → rozszerzyć o `uczelnia`
   (z `bpp_jednostka.uczelnia_id`); pipeline temp-tabel (`bpp_temporary_cpaq*`,
   `bpp_temporary_cpasg*`) musi nieść uczelnię.
3. **ewaluacja_metryki** — `views/{detail,list}.py` read-only (prosty filtr);
   `views/pin_unpin.py` to write-path (już OK, rebuild liczy wszystkie uczelnie).
4. **oswiadczenia**, **ewaluacja_common** (`utils.py`), **bpp/core.py**,
   `management/commands/zbieraj_sloty.py` — read-only; status priorytetu „do ustalenia".
5. **ewaluacja2021 / raporty 3N** — STATUS NIEJASNY: web URL-e wyłączone, ale
   żywe mgmt-commands (`raport_3n_*`, `przelicz_liczbe_n_dla_uczelni`,
   `odepnij_dyscypliny`) + import `const` w `ewaluacja_common`. Decyzja
   „używać/naprawiać?" do podjęcia (najpierw potwierdzić użycie 3N).
6. „Liczba N", rankingi, API — konsumują cache pośrednio (`Rekord`/serializery);
   zweryfikować czy filtrują, czy idą przez widok.

### B) ODŁOŻONE (trudniejsze): federacja optymalizacji
**ewaluacja_optymalizacja** (`core/*`, `tasks/unpinning/*`, `utils.py`, `views/*`)
i **ewaluacja_optymalizuj_publikacje** (`views.py`). Instalacja wielouczelniana to
**federacja** — optymalizacja (dobór przypięć/dyscyplin) musi maksymalizować wynik
w obrębie CAŁEJ federacji, nie pojedynczej uczelni. To NIE prosty filtr per-uczelnia
— inny problem optymalizacyjny ponad partycjonowanym cache. Write-path (rebuild po
zmianie) już poprawny; logika decyzyjna federacyjna odłożona. Osobny, późniejszy spec.

### C) Backlog hardeningu z self-review (MEDIUM/LOW — wpiąć w read-side/federację)
1. **[MEDIUM] `_dopasuj_kalkulator` liczy `wiele_hst`/próg globalnie** (wszystkie
   uczelnie), kalkulator używany per-uczelnia → rekord cross-uczelnia mieszający
   HST/nie-HST ponad granicą uczelni dziedziczy globalne `wiele_hst`. Spec to
   akceptuje, brak testu. Dodać test graniczny + jawną decyzję domenową.
2. **[MEDIUM] brak indeksu** `(rekord_id, uczelnia, dyscyplina)` na
   `Cache_Punktacja_Dyscypliny` (jest tylko `(uczelnia, dyscyplina)`) — pod join
   widoku i jako naturalny klucz. Dorzucić w nowej migracji.
3. **[LOW] asymetria `skupia_pracownikow`** (pre-existing): `_zapisz` filtruje,
   `autorzy_z_dyscypliny` (→ `k`, → lista w CPD) nie → CPD może listować PK autora
   bez wiersza CPA. Istotne dla read-side (zaskoczenie konsumenta) — udokumentować/zrównać.
4. **[LOW/design] mutacja `kalk.uczelnia` po konstrukcji** w `ISlot` — bezpieczna
   tylko dzięki świeżej instancji. Rozważyć `uczelnia` jako wymagany arg konstruktora.
5. **NOT NULL na `Cache_Punktacja_Dyscypliny.uczelnia`** — niemożliwe dopóki
   fixtures tworzą NULL w runtime; rozważyć po uporządkowaniu fixtures (read-side).

### D) Integrator per-uczelnia (parked)
`pbn_integrator/utils/scientists.py` (matcher), `importer/authors.py` (×5 porównań
afiliacji), `management/commands/pbn_integrator.py`. Porównania z „naszą" uczelnią
(`objects.default.pbn_uid_id`) — wymaga przekazania uczelni docelowej przez pipeline.
`objects.default` zostaje świadomie (perf w pętlach).

### E) Drobne
- Usunięcie fallbacku `get_default` z `adapters/wydawnictwo.py` — wymaga migracji
  testów adaptera + naprawy `pbn_wyslij` (pre-existing `C901`). Niski priorytet.

### F) Operacyjne (deploy write-side)
- Single-install: migracja 0425 sama wpisze ID domyślnej uczelni w legacy cache;
  pełny denorm rebuild odświeży liczby (identyczne). Multi-install z danymi:
  migracja 0425 **failuje** dopóki cache nie zostanie przeliczony per-uczelnia.

---

## ROADMAPA (rekomendowana kolejność — ustalona z userem 2026-06-03)

Zatwierdzony wariant: **A (Verify → Stabilize → Investigate → Spec)**.

1. ✅ **Self-review write-side** (zrobione) — + fix migracji 0425.
2. ✅ **Aktualizacja HANDOFF + roadmapa** (ten dokument).
3. ⏭ **Read-side discovery** — rozstrzygnąć statusy „do ustalenia" FAKTAMI z kodu
   (ewaluacja2021/3N czy żywe; liczba N/rankingi/API — bezpośrednio cache czy przez
   `Rekord`; realny kształt oswiadczenia/ewaluacja_common/bpp core). Output:
   zredukowana lista decyzji.
4. ⏭ **Brainstorm → spec read-side → plan** (`writing-plans`). Federacja (B) NIE
   wchodzi — osobny, późniejszy spec.
5. (później) Federacja optymalizacji; integrator (D); drobne (E).

Backlog hardeningu (C) wpinać oportunistycznie w Krok 4 (te dotykające read-side:
indeks #2, asymetria #3) i federację (#1 HST).

---

## KOMENDY (dla agenta)
- Testy: `uv run pytest <ścieżka> -q -p no:cacheprovider` (testcontainers same
  stawiają PG/Redis; Docker musi działać).
- Guard: `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q`.
- Sloty (invariant): `uv run pytest src/bpp/tests/test_models/test_sloty/ src/raport_slotow/ -q -p no:cacheprovider`.
- Lint: `uv run ruff check <pliki>` (NIE `--fix`; per CLAUDE.md fix ręcznie).
- `uv run python src/manage.py makemigrations --check --dry-run` (z
  `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1` gdy brak dev-bazy).
