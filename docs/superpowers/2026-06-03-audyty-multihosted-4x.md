# Audyty multi-hosted (4×) — raport 2026-06-03

Cztery audyty wykonane po domknięciu głównych wątków multi-hosted (write/read
sloty, liczba_n R2, integrator, HST, NOT NULL, verify.py). Wszystkie read-only.
Metoda: trzy audyty rozpoznawcze (1–3) równolegle przez subagentów, potem
audyt 4 (self-review vs spec) rozbity na 4 recenzentów per obszar.

Gałąź: `feature/multi-hosted-config` (HEAD `88b688dbc` w chwili audytu).

---

## NAJWAŻNIEJSZY WNIOSEK (zbieżność audytów 3 + 4b)

Dwa niezależne audyty wskazały **to samo**: publiczne widoki czytające `Rekord`
**wprost** przeciekają dane międzyuczelniane. R1 świadomie objął tylko *cache
slotów* (`Cache_Punktacja_*`), więc to NIE regresja R1 — ale spec R1 **nie
odnotował** tych widoków jako wyłączonych z zakresu, więc grożą zgubieniem
(„read-side wygląda na zamknięty po R1", a najwidoczniejszy przeciek zostaje).

→ Kandydat na osobny wątek **R3 (read-side publiczny Rekord)**. Patrz backlog A.

---

## Audyt 1 — `get_default`/`objects.default` poza świadomym „zostaje"

Źródło prawdy: `src/bpp/tests/test_multihosted_get_default_guard.py` (`APPROVED`).
Guard szczelny — grep wzorcem guarda daje dokładnie whitelistę, nic ponad.
Szersze trafienia (`Engine.get_default()`, docstringi tasków opisujące że kod
*nie* robi get_default, definicje `self.get_default()` w managerze) to
false-positives względem celu.

**9 wpisów ZOSTAJE** (legit): `middleware.py:295` (fallback Site bez Uczelni),
`bpp_specific.py:104` (request-first, fallback bez requestu CLI/Celery),
`abstract/pbn.py:25,93` (None-tolerant warstwa modelu, linki PBN),
`jednostka.py:48` (sort/display), `numeric_fields.py:73` (toggle IC None-tolerant),
`ewaluacja2021/util.py:113` (komentarz), `pbn_api/.../util.py:54` (guarded
count==1, wzorcowy CLI), `pbn_import_tags.py:23` (request-first), `command_helpers.py:43`
(CLI None-tolerant + CommandError).

**1 wpis DO ZROBIENIA:**

| plik:linia | werdykt | jak naprawić |
|---|---|---|
| `powiazania_autorow/queries.py:189` (`_pbn_root()`) | **DO ZROBIENIA** | Oba call-sites to `View.get(self, request, pk)` (`powiazania_autorow/views.py:48`, `:140`) — request dostępny. Zmienić `_pbn_root()` → `_pbn_root(uczelnia)`; w widokach `_pbn_root(Uczelnia.objects.get_for_request(request))`. Argument „anty-N+1" (root raz) jest ortogonalny do *którą* uczelnię. Bug kosmetyczny (zły host PBN w linkach grafu uczelni B), ale realny. Komentarz „deferred multi-host" = dług, nie świadoma decyzja. |

---

## Audyt 2 — taski Celery bez argumentu `uczelnia`

**Cała warstwa PBN (wysyłka/pobieranie/import) poprawnie naprawiona** — jawny
`uczelnia_id` + `get_for_pbn_background`/FK wpisu kolejki/`session.uczelnia`,
zero `get_default()`/`get_for_request()` w tle. Wzorcowe: `pbn_export_queue`,
`pbn_downloader_app`, `pbn_import`, `importer_publikacji`, `pbn_wysylka_oswiadczen`,
`oswiadczenia.generate_oswiadczenia_zip`, `bpp.zaktualizuj_liczbe_cytowan` (pętla
per uczelnia).

Realne gapy = taski które **mają** `uczelnia_id`, ale globalne querysety go
ignorują (mieszają/kasują dane wszystkich uczelni):

| task (plik:linia) | problem | ryzyko / klasyfikacja |
|---|---|---|
| `solve_single_discipline_task` (`ewaluacja_optymalizacja/tasks/optimization.py:73`) | `OptimizationRun.objects.filter(dyscyplina_naukowa=dyscyplina).delete()` bez `uczelnia=` → kasuje runy innych uczelni dla wspólnej dyscypliny; `solve_discipline(dyscyplina_nazwa=...)` nie dostaje uczelni | ŚREDNIE — **federacja olana, ale to korupcja danych, nie logika federacyjna** |
| `reset_all_pins_task` (`tasks/reset_pins.py:139`) | `Autor_Dyscyplina.filter(rok__gte=2022, rok__lte=2025)` globalnie (task ma `uczelnia_id`) | ŚREDNIE — federacja |
| `optimize_and_unpin_task` (`optimization.py:536,573`) | `Wydawnictwo_*_Autor.filter(przypieta=True)` globalnie | ŚREDNIE — federacja |
| `porownaj_dyscypliny_pbn_task` (`komparator_pbn_udzialy/tasks.py`, `utils.py:46`) | iteruje `OswiadczenieInstytucji.objects.all()` + globalny `.delete()` rozbieżności; brak arg `uczelnia` (call-site `views.py:316` ma request) | ŚREDNIE — czyta lokalny cache, nie crashuje |
| `porownaj_zrodla_task` (`pbn_komparator_zrodel/tasks.py:13`, `utils.py:227`) | `RozbieznoscZrodlaPBN.objects.all().delete()` globalnie; model bez FK uczelni → realnie NISKIE | NISKIE (dane źródeł globalne) |
| `generuj_metryki_task` (`ewaluacja_metryki/tasks.py:245`, `utils.py:556`) | `MetrykaAutora.objects.all().delete()` — model **bez FK uczelnia**; jawne komentarze „rewizja per-uczelnia = federacja" | ŚREDNIE — **świadomy deferral** (patrz backlog D) |

Niuans krytyczny: optymalizacja jest świadomie olana, ale `OptimizationRun.delete()`
cross-uczelnia to *korupcja danych*, a nie *decyzja optymalizacyjna federacyjna*.
Minimalny scope-fix delete'ów można rozważyć niezależnie od reszty federacji.

---

## Audyt 3 — gdzie jeszcze uczelnia się przyda (read-side runtime)

Architektura: każda uczelnia na własnej domenie (`Site`); middleware ustawia
`request._uczelnia`; `get_for_request` zwraca uczelnię z domeny. Dane NIE
partycjonowane — atrybucja przez `autor → jednostka.uczelnia` (`skupia_pracownikow=True`).
Strona główna (`get_uczelnia_context_data`) JUŻ scopuje. Każdy publiczny
`Rekord.objects.all()` na domenie uczelni = przeciek.

**5 realnych gapów (publiczna strona, wszystkie mają `get_for_request` w zasięgu):**

| # | miejsce (plik:linia) | co | ruch |
|---|---|---|---|
| 1 | `bpp/views/mymultiseek.py:37` (→ `multiseek_registry/__init__.py:32` `Rekord.objects.all()`) | **multiwyszukiwarka** — tylko `ukryte_statusy`, brak filtra uczelni; agregaty `ctx["sumy"]` z tego samego qs | NAJWYŻSZY |
| 2 | `nowe_raporty/poziomy.py:39-42` (`_base_uczelnia`, woła `views.py:286`) | **raport „cała uczelnia"** — `obiekt`=uczelnia PRZEKAZANY ale IGNOROWANY (`Rekord.objects.all()`) | wysoki, najbardziej rażący |
| 3 | `ranking_autorow/views.py:265-291` (`Sumy`) | **ranking autorów** — filtr `jednostka__uczelnia` tylko gdy user ręcznie wybierze jednostkę; domyślnie globalny | wysoki |
| 4 | `bpp/views/browse.py:491-556` (`LataView`, `RokView`) | **browse lata/rok** — `Rekord` globalnie | średni |
| 5 | `bpp/views/oai.py:243-247` (`OAIView`) | **OAI-PMH** — `Rekord.objects.all()`, tylko `ukryte_statusy("api")`; harvester pobiera cudze rekordy | publiczny eksport |

Wzorzec naprawy jednolity:
`.filter(autorzy__jednostka__uczelnia=uczelnia, autorzy__jednostka__skupia_pracownikow=True).distinct()`
(join przez `autorzy` mnoży wiersze → `distinct`). Rekomendacja: wspólny helper
`scope_rekord_do_uczelni(qs, uczelnia)` (analogicznie do `Rekord.objects.prace_jednostki`),
by nie powielać reguły `skupia_pracownikow` w 5 miejscach.

**OK-świadome / minor (niski impakt, istotne tylko gdy uczelnie mają różne rooty PBN):**
`abstract/pbn.py:25,93` (`link_do_pbn`/`_format_link_pi` → `get_default().pbn_api_root`),
`powiazania_autorow/queries.py:189` (ten sam co Audyt 1),
`numeric_fields.py:73` (toggle IC). API REST (`api_v1/viewsets/*`) listuje globalnie
po modelu — to API maszynowe, osobny temat, nie blokuje.

---

## Audyt 4 — self-review kodu vs SPEC i PLAN

### 4a. Sloty WRITE-SIDE — ✓ kompletne (31/31 punktów)
Spec `2026-06-02-per-uczelnia-sloty-design.md`, plan `2026-06-02-per-uczelnia-sloty.md`.
Testy lokalnie: 18/18 `test_per_uczelnia.py`, 79/79 `test_sloty/`, brak dryfu migracji.

- **1 świadomy, KORZYSTNY rozjazd:** spec mówił „wybór progu uczelnia-niezależny",
  ale kod liczy `wiele_hst`/HST per-uczelnia (`core.py:73` `_dopasuj_kalkulator(original, uczelnia)`
  + `wszystkie_dyscypliny_rekordu(uczelnia)`, commit `c687ceb07`). Lepsze niż spec
  — globalne `wiele_hst` psułoby liczby cross-uczelnia. `canAdapt()` woła bez uczelni
  (boolean adapt-check) — OK. **Rekomendacja:** dopisać notkę do spec, że reguła
  „próg uczelnia-niezależny" została zrewidowana dla `wiele_hst`.
- **Stary self-review PRZETERMINOWANY:** `reviews/2026-06-03-self-review-per-uczelnia-sloty-write-side.md`
  zgłaszał jako otwarte: NOT NULL (niemożliwe), brak indeksu, widok bez uczelni —
  wszystkie od tego czasu domknięte (`6c888f245`+mig 0428, mig 0427, mig 0426).
  **Rekomendacja:** oznaczyć go jako SUPERSEDED.
- Brak twardych luk. Pozostałe LOW: mutacja `kalk.uczelnia` po konstrukcji
  (bezpieczna przy świeżej instancji), asymetria `skupia_pracownikow` (pre-existing,
  udokumentowana `core.py:411-419`).

### 4b. Sloty READ-SIDE R1 — ✓ z 1 luką (18/19)
Spec `2026-06-03-per-uczelnia-sloty-read-side-design.md`, plan `…-R1.md`.

- **LUKA (jedyna, realna):** komenda CLI `zbieraj_sloty`
  (`bpp/management/commands/zbieraj_sloty.py:36-38`) NIE obsługuje uczelni —
  woła `autor.zbieraj_sloty(slot, rok_min, rok_max)`; wrapper `Autor.zbieraj_sloty`
  (`autor.py:383-402`) NIE przekazuje `uczelnia_id` do `bpp.core.zbieraj_sloty`;
  brak argumentu `--uczelnia`. Spec wymieniał ją **dwukrotnie** (single-or-fail /
  argument). Plan Task 4 pokrył tylko funkcję `bpp.core.zbieraj_sloty`, self-review
  planu po cichu pominął CLI. Single-install no-op → niewidoczne w testach.
  **Fix:** dodać `uczelnia_id` do `Autor.zbieraj_sloty` (przelot do core) +
  `--uczelnia` + `.get()` single-or-fail w komendzie.
- **ROZJAZD łagodny:** API `raport_slotow_uczelnia` filtruje per-OWNER
  (`viewsets/raport_slotow_uczelnia.py:38`), nie per-UCZELNIA. Bezpieczne (brak
  przecieku do innego usera), zgodne z dopuszczeniem planu. Edge: superuser z
  override `?uczelnia=` widzi przez API raporty wszystkich uczelni naraz. Niski
  priorytet; dopisać do spec że dla R1 ownership ≈ uczelnia.
- **Scope gaps (poza spec):** 5 publicznych czytników `Rekord` = zbieżne z Audytem 3.

### 4c. liczba_n R2 — ✓ kompletne (24/24)
Spec `2026-06-03-ewaluacja-liczba-n-per-uczelnia-design.md`, plan `…-R2.md`.
Testy: 20 passed / 1 skipped, brak dryfu migracji.

- FK `uczelnia` na obu `IloscUdzialow*` + `unique_together` z uczelnią ✓; backfill
  0009 (single→domyślna / multi→fail) ✓; główny bug `oblicz_sumy_udzialow_za_calosc`
  `objects.all().delete()` → `filter(uczelnia=...).delete()` ✓ (`utils.py:221`);
  atrybucja `aktualna_jednostka.uczelnia` + `skupia_pracownikow`, NULL/obca wykluczeni
  ✓; widoki list/export/verify filtrują `get_for_request` ✓.
- Oba minory follow-up z HANDOFF **DOMKNIĘTE:** verify.py Autor_Dyscyplina globalnie
  → `ee67eb958`; admin nie pokazywał uczelni → `6c888f245`.
- **Poza zakresem (świadomie):** `ewaluacja_metryki` czyta
  `IloscUdzialowDlaAutoraZaCalosc.objects.all()` globalnie w 5 miejscach
  (`tasks.py:231,357`, `utils.py:277`, `oblicz_metryki.py:132`, `generation.py:74`).
  Spec umieścił metryki poza R2. Patrz backlog D.

### 4d. Integrator — ✓ kompletne (16/16)
Spec `2026-06-03-integrator-per-uczelnia-design.md` (bez osobnego planu — subagent-driven).

- Wszystkie 3 sites: authors.py 5× `uczelnia.…`/`client.uczelnia` ✓; command
  `_handle_people` → `client.uczelnia.pbn_uid_id` ✓; matcher
  `matchuj_autora_po_stronie_pbn(…, uczelnia)` + caller `autor.aktualna_jednostka.uczelnia`/None ✓.
- Świadoma delta R2 (`aktualna_jednostka=None` → matcher zwraca `None`) obecna i
  zgodna (`scientists.py:433-447`). `_przetworz_afiliacje` keyword-only `uczelnia`
  (code review `a982dbfe7`). `pbn_integrator/` czyste z `objects.default`.
- **2 nieblokujące:** brak testu na deltę R2 (`uczelnia=None`→`None`) — pre-existing
  gap, spec testu nie wymagał; stale docstring matcha/`_handle_people` (brak `uczelnia`
  w `Args:`). Spec-bez-planu wystarczył dla 3-site mechanicznej zmiany + 1 reguły.

---

## SKONSOLIDOWANY BACKLOG (priorytety)

### A. Read-side publiczny `Rekord` (R3) — NOWY WĄTEK, najwyższy priorytet
5 widoków (Audyt 3/4b): multiwyszukiwarka, raport-uczelnia, ranking, browse lata/rok,
OAI. Najwidoczniejszy przeciek. Wspólny helper `scope_rekord_do_uczelni` + filtr
`autorzy__jednostka__uczelnia` + `skupia_pracownikow` + `distinct`. Każdy ma już
`get_for_request` w zasięgu. → brainstorm→spec→plan→subagent.

### B. Drobne, gotowe-do-zrobienia (małe, lokalne)
- `powiazania_autorow/queries.py:_pbn_root()` → `get_for_request` (Audyt 1).
- `zbieraj_sloty` CLI + `Autor.zbieraj_sloty` → `uczelnia_id` (LUKA R1, Audyt 4b).
- Test na deltę R2 integratora (`uczelnia=None`→`None`) + docstringi (Audyt 4d).
- Oznaczyć stary self-review write-side jako SUPERSEDED; dopisać notkę HST do spec
  write-side (Audyt 4a).
- (opcjonalnie) dopisać do spec R1, że ownership API ≈ uczelnia.

### C. Federacja olana — ale z bugami korupcji danych
`OptimizationRun.delete()` / `reset_pins` / `optimize_and_unpin` /
komparatory PBN globalne `.delete()` (Audyt 2). DECYZJA: minimalny scope-fix
delete'ów teraz (chroni przed kasowaniem cudzych danych), czy całość z federacją
później? Logika decyzyjna federacyjna pozostaje olana — ale delete cross-uczelnia
to inna kategoria (integralność, nie optymalizacja).

### D. `ewaluacja_metryki` per-uczelnia — OSOBNY WĄTEK (write+read)
`MetrykaAutora` bez FK `uczelnia` + 5 globalnych `IloscUdzialow…objects.all()`
(Audyt 2/4c). Wymaga migracji (FK + backfill jak 0009/0425) + scope delete/generate.
Analogiczny kształt do liczba_n R2.

---

## Świadomie OLANE (nie ruszać bez osobnej decyzji)
Federacja optymalizacji jako *logika decyzyjna* (`ewaluacja_optymalizacja` dobór
przypięć/dyscyplin ponad partycjonowanym cache, `ewaluacja_optymalizuj_publikacje`).
UWAGA: to NIE to samo co bugi korupcji danych z backlogu C — te ostatnie warto
rozważyć niezależnie.
