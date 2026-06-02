# HANDOFF — praca multi-hosted (stan na 2026-06-02)

Notatka do wznowienia po reset/compact sesji. Gałąź: `feature/multi-hosted-config`.
Wszystko zacommitowane i **wypushowane** (origin na `a834691fd`).

Kontekst projektu: BPP (Django), instalacja **wielouczelniana** — jedna instancja
obsługuje wiele obiektów `Uczelnia`, każda z własną konfiguracją (PBN tokeny,
flagi wyświetlania itd.). Cel całości: żaden runtime nie „zgaduje" uczelni
(`get_default()` = pierwsza-z-brzegu), tylko używa właściwej.

---

## CO ZROBIONE (2 duże wątki, oba domknięte)

### Wątek 1: rozbicie `PBNClient` na dwie warstwy (Wariant B)
Spec: `docs/superpowers/specs/2026-06-02-pbn-client-split-design.md`

- **`src/pbn_client/`** — czysta, reusable warstwa protokołu PBN (transport,
  auth, pagination, mixiny słownikowo-CRUD, `StatementsMixin`, `PBNClient`).
  **Zero importów `bpp`/`pbn_api`** (zweryfikowane). Kandydat na osobny pakiet.
- **`BppPBNClient`** w `pbn_api/client/__init__.py` — dziedziczy po `PBNClient`,
  dokłada orchestrację (`publication_sync`, `disciplines`) i **zna swoją
  `Uczelnia`** (`__init__(transport, uczelnia)`). `get_default()` zniknął z
  `publication_sync` i z głównej ścieżki adaptera (orchestracja przekazuje
  `uczelnia=self.uczelnia`).
- Fabryki: `Uczelnia.pbn_client()`, `PBNBaseCommand.get_client()`, fixtura
  `pbn_client` → zwracają `BppPBNClient`. `pbn_api.client` to shim
  re-eksportujący pełny `__all__` (kompatybilność wsteczna, 35 importów).
- `pbn_api/const.py`, `exceptions.py`, `client/transport.py`, `utils.py` →
  shimy do `pbn_client`. `pbn_api/utils.py` → shim do `pbn_client/dict_utils`.
- Wariant B (NIE było osobnego pakietu `pbn_client_bpp`): orchestracja i
  adaptery **zostają w `pbn_api`**. Dlaczego: ekstrakcja `pbn_api` i tak
  zablokowana przez sklejenie modeli z `bpp` — patrz audyt.
- Test multi-hosted: `src/pbn_api/tests/test_multihosted.py` (dwie uczelnie →
  klient czyta flagi ze SWOJEJ).

### Wątek 2: cleanup `get_default` (Fazy 1–9) — KOMPLETNY
Plan: `docs/superpowers/plans/2026-06-02-get-default-cleanup.md`
Audyt + status: `docs/deweloper/audyt-multihosted-pbn.md`

Reguła binarna (ustalona z userem): runtime z dostępną uczelnią → **jawna
uczelnia** (`get_for_request` / argument / FK / `self.uczelnia`); reszta
akceptowalna → **`Uczelnia.objects.get()`** (single-or-fail; NIE nowa metoda).

- Fazy 1–8 przepięły runtime na jawną uczelnię; fallbacki single-install na
  `.get()`. **Rygor per-miejsce** (na życzenie usera) wyłapał 3 miejsca, gdzie
  mechaniczne `.get()` było złe → cofnięte do None-tolerant/lazy:
  `adapters/wydawnictwo.py` (test-only fallback), `command_helpers.py`
  (clean `CommandError`), `oblicz_metryki.py` (lazy uczelnia w gałęzi liczby-N).
- **Faza 9 = guard:** `src/bpp/tests/test_multihosted_get_default_guard.py` —
  zamraża whitelistę 15 świadomych miejsc; nowy `get_default` w runtime →
  fail CI. (Whitelista + uzasadnienia w tym teście i w audycie.)
- Weryfikacja: **1302 passed, 2 skipped** na dotkniętym obszarze.

---

## CO ZOSTAŁO (PARKED — następne wątki)

### A) NASTĘPNY: per-uczelnia liczenie slotów/punktacji  ← brainstorm tutaj
Parked TODO w: `bpp/models/sloty/core.py` (`ISlot`),
`bpp/models/abstract/disciplines.py` (`przelicz_punkty_dyscyplin`).

**Ustalenia domenowe (od usera, KLUCZOWE):**
- Rekord NIE ma deterministycznej uczelni — autorzy mogą być z różnych uczelni
  (autor → afiliacja na jednostkę → jednostka ma uczelnię). Praca z autorami
  z 10 uczelni → sloty trzeba policzyć i zapisać **osobno per uczelnia**.
- Matematyka slotów zależy od **ROKU**, nie uczelni. Z uczelni `ISlot` czyta
  TYLKO `ukryte_statusy("sloty")` (rzadki filtr: „nie licz dla statusu X").
- **Pomysł usera (tani rdzeń):** `Cache_Punktacja_Autora` jest JUŻ per-autor →
  dorzucić `uczelnia_id` (= uczelnia jednostki autora) = otagowanie istniejących
  wierszy, nie sztuczne mnożenie.

**Co spec musi rozstrzygnąć (głębia):**
1. `Cache_Punktacja_Dyscypliny` to agregat per (rekord, dyscyplina) → rozbić
   per (rekord, uczelnia, dyscyplina); liczenie iteruje uczelnie rekordu.
2. `ukryte_statusy` per uczelnia — `ISlot` biegnie per uczelnia z JEJ statusami
   (rekord policzony dla Y, pominięty dla X).
3. Migracja + backfill (`uczelnia_id` z jednostki autora; single-install →
   jedna uczelnia, zero zmiany zachowania).
4. ODCZYTY: raporty, rankingi, „liczba N", `ewaluacja_optymalizacja`, metryki,
   API — filtrować po uczelni oglądającego (`get_for_request`). Duży, jednorodny
   zbiór.
5. Invalidacja przy zmianie afiliacji autora; indeksy/objętość.

### B) Integrator per-uczelnia (parked TODO)
`pbn_integrator/utils/scientists.py` (matcher), `importer/authors.py` (×5
porównań afiliacji), `management/commands/pbn_integrator.py` (`_handle_people`).
Porównania z „naszą" uczelnią (`objects.default.pbn_uid_id`) — wymaga przekazania
uczelni docelowej przez pipeline integratora (deeper). `objects.default` zostaje
świadomie (cached; `.get()` byłby perf-regresją w pętlach + crash na >1).

### C) Drobne
- Pełne usunięcie fallbacku `get_default` z `adapters/wydawnictwo.py` — wymaga
  migracji testów adaptera (konstruują bez uczelni) + naprawy `pbn_wyslij`
  (pre-existing `C901`). Niski priorytet (runtime przekazuje jawną uczelnię).

---

## STAN GIT
- Gałąź `feature/multi-hosted-config`, origin = `a834691fd` (wypushowane).
- Główne commity (od najnowszych): plan/audyt docs, Faza 9 guard, Fazy 8→1
  get_default, Faza 2+3 ImportManager, importer_publikacji `ImportSession.uczelnia`.

## KOMENDY (dla agenta)
- Testy: `uv run pytest <ścieżka> -q -p no:cacheprovider` (testcontainers same
  stawiają PG/Redis; Docker musi działać).
- Guard: `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q`.
- Lint: `uv run ruff check <pliki>` (NIE `--fix`; per CLAUDE.md fix ręcznie).
- `uv run python src/manage.py check` (z `PYTEST_TESTCONTAINERS_DISABLE=1
  DJANGO_BPP_SKIP_DOTENV=1` gdy brak dev-bazy).
