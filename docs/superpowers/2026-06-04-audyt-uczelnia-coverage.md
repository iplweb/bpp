# Audyt pokrycia uczelnia (multi-hosted) — raport 2026-06-04

Audyt **read-only** pokrycia bugów multi-hosted po domknięciu głównych wątków
(write/read sloty R1, liczba_n R2, R3a/R3b publiczny, integrator, metryki D,
drobne B1–B6). Cel: zweryfikować systematycznie, że nie ma niezałatanego buga.

Metoda: recon (HANDOFF + Audyt 4× + guard) → 6 równoległych subagentów-audytorów
po obszarach (`bpp/views`, `bpp/models`, `api_v1`, `pbn_api`+integrator+komparatory,
`raport_slotow`+`ewaluacja_*`, `powiazania_autorow`+commands+admin) → osobista
weryfikacja każdego czystego 🔴 → synteza. Gałąź `feature/multi-hosted-config`.

Klasyfikacja statusów odzwierciedla **decyzje produktowe usera z 2026-06-04**
(sekcja „Decyzje usera" niżej).

---

## Klasa 1 — `get_default()` / `objects.default` (guard)

**Guard zielony** (`test_multihosted_get_default_guard.py` — 1 passed). Whitelista
= **9 plików**, wszystkie ZOSTAJĄ (świadome fallbacki bez requestu / None-tolerant
warstwa modelu / display / guarded count==1 / komentarz). Weryfikacja każdego wpisu
(Audyt 1 z 4× + ponowny grep): brak ukrytej luki runtime. Poza whitelistą — nic
(potwierdzone regexem; warianty `Jednostka.objects.get_default_ordering` i
`self.get_default()` w definicji managera nie pasują do wzorca i NIE są bugiem).

### 🔴 NOWE: druga ślepa plamka guarda — `Uczelnia.objects.first()`

Guard pilnuje wyłącznie `get_default()`/`objects.default`. Wzorzec **równoważny
semantycznie** (zgadnij pierwszą-z-brzegu uczelnię) `Uczelnia.objects.first()`
występuje **28×** w runtime, zdominowany przez widoki `ewaluacja_optymalizacja`:

| plik | liczność |
|---|---|
| `ewaluacja_optymalizacja/views/evaluation_browser/views.py` | 6 |
| `ewaluacja_optymalizacja/views/{unpinning_list,pins,optimize_unpin,discipline_swap_list}.py` | 2 każdy |
| `ewaluacja_optymalizacja/views/{unpinning_analysis,unpin_sensible,index,discipline_swap_analysis,bulk_optimization}.py` | 1 każdy |
| `ewaluacja_optymalizacja/{management/commands,core}` | 3 |
| `bpp/models/{jednostka,autor}.py`, `bpp/admin/core.py`, demo/debug | po 1 (warstwa modelu/UI/demo — niska waga) |

To ten sam klasa-ryzyka co pierwotny bug B1, ale niewidoczny dla guarda. W widokach
`ewaluacja_optymalizacja` (request dostępny) `Uczelnia.objects.first()` → optymalizacja
DLA PIERWSZEJ uczelni niezależnie od hosta. **Rekomendacja:** rozszerzyć guard o
wzorzec `Uczelnia\.objects\.first\(\)` (z whitelistą dla demo/debug/warstwy modelu).

---

## Klasa 2 — brakująca uczelnia (znaleziska)

### 🔴 LUKI — do naprawy (zweryfikowane osobiście, decyzje usera wbudowane)

| # | plik:linia | znalezisko | reguła naprawy (decyzja usera) |
|---|---|---|---|
| 1 | `bpp/models/cache/rekord.py:302-328` | `punktacja_autora`/`punktacja_dyscypliny`/`ma_punktacje_sloty` filtrują tylko `rekord_id` → **publiczna strona rekordu** pokazuje CPD/CPA wszystkich uczelni. Szablony (`browse/praca_tabela*.html`) mają `uczelnia` w kontekście. R3a objął listy, nie szczegół rekordu. | rekord wyszukiwalny globalnie; tabelka punktacji zawężona: CPA przez `jednostka__uczelnia`, CPD przez `uczelnia` oglądającego. Guard `tylko_jedna_uczelnia()` no-op. |
| 2 | `bpp/views/profile.py:21` | `MetrykaAutora.objects.filter(autor=autor)` bez uczelni — profil pokazuje metryki ze WSZYSTKICH uczelni autora (przeoczenie wątku D — D objął `ewaluacja_metryki/views/`, nie profil w `bpp/views/`). | pokaż, ale tylko z JEDNEJ uczelni — tej z requestu: `scope_metryki(qs, uczelnia_dla_odczytu(request))`. |
| 3 | `bpp/views/autocomplete/navigation.py:130-190` (+ `search_services.py`) | publiczny `GlobalNavigationAutocomplete` (bez auth) szuka jednostek/autorów/rekordów globalnie, tylko `ukryte_statusy("podglad")`. R3b objął dedykowane pickery (`UczelniaScopedAutocompleteMixin`), ten global-search pominął. | jednostki: filtr `uczelnia`; autorzy: „ma ≥1 jednostkę z uczelni" (reguła R3b autor: `aktualna_jednostka__uczelnia` OR `autor_jednostka__jednostka__uczelnia`); rekordy: przez `autorzy__jednostka__uczelnia`. |
| 4 | `bpp/views/autocomplete/simple.py:74` | `LataAutocomplete` — `Rekord.objects.all()` globalnie; niespójne z zawężonym `LataView` (R3a). | zawęź przez `autorzy__jednostka__uczelnia` (jak rekordy wyżej). |
| 5 | `raport_slotow/views/zerowy.py:80` | `autorzy_zerowi(min_pk, od_roku, do_roku)` bez `uczelnia=` → strona „existent" liczona z punktów wszystkich uczelni; autor z punktami tylko na uczelni B błędnie wykluczony z raportu zerowego uczelni A. **Połowiczny fix** (commit `29734f833` dodał parametr do `core.py`, call-site go nie przekazuje). | `uczelnia=uczelnia_dla_odczytu(self.request)`. `Cache_Punktacja_Autora_Query_View` ma kolumnę `uczelnia` (autor→jednostka→uczelnia w każdej pracy) — `autorzy_z_punktami` już filtruje po niej. |
| 6 | `pbn_api/models/sentdata.py` (`SentDataManager`) + `pbn_api/client/publication_sync.py:204-238` | `SentData` ma nullable FK `uczelnia`, ale `get_for_rec` szuka po `(object_id, content_type)` bez uczelni, a żadna metoda nie ustawia/filtruje `uczelnia`. Dwie uczelnie wysyłające ten sam rekord **współdzielą i nadpisują** jeden wiersz → `bad_uploads`/`check_if_upload_needed`/`only_new` błędnie pomijają wysyłkę do drugiego profilu PBN (zgubiona wysyłka). | tagować per-uczelnia: rekord na 2-3 profile instytucji → 2-3 osobno oznaczone `SentData`; klucz lookup `(object_id, content_type, uczelnia)`. Wymaga migracji + backfill. |
| 7 | `oswiadczenia/tasks.py:117` + `views.py:89,191,375` | „Wydruk oświadczeń 2022-25" (lista HTML, XLSX, ZIP/PDF/DOCX) buduje qs `Autorzy` tylko po roku/autorze/tytule/dyscyplinie — bez `jednostka__uczelnia` → admin widzi/eksportuje oświadczenia WSZYSTKICH uczelni. Wzorzec poprawny obok: `OswiadczeniaPublikacji.get_context_data` (views.py:346). | scope qs przez `jednostka__uczelnia=uczelnia_dla_odczytu(request)`. |
| 8 | `oswiadczenia/tasks.py:539,559` + `views.py:512` | `generate_oswiadczenia_zip` ma `uczelnia_id=None`→`Uczelnia.objects.get()`; widok robi `.delay(task.pk)` bez `uczelnia_id`, model `OswiadczeniaExportTask` bez pola uczelnia → multi-install **crash** `MultipleObjectsReturned`. (Korekta briefu: NIE jest „per uczelnia".) | przekazać `uczelnia_id` do taska (z `get_for_request`); dodać pole/przelot. |
| 9 | `zglos_publikacje/views.py:238` + `forms.py:303,316` + `models.py:253-256` | Wizard zgłaszania publikacji: widok zna uczelnię (`dispatch`), ale `get_form_kwargs` nie przekazuje jej do formy → `Uczelnia.objects.get()` → `MultipleObjectsReturned`. `Zgloszenie_Publikacji._uczelnia` nigdy nie ustawiane → ta sama awaria w walidacji opłat. **Publiczny wizard niedziałający w multi-hosted.** | przekazać `uczelnia` do `get_form_kwargs`/`form.__init__` i ustawić `instance._uczelnia`. |
| 10 | `bpp/management/commands/wyczysc_baze.py:60-66,136` | Komenda rozwiązuje `uczelnia` i drukuje „Baza danych czyja?", ale kasuje `klass.objects.all().delete()` **globalnie** — `wyczysc_baze --uczelnia=2` wyczyści dane wszystkich uczelni. UI sugeruje scope, kod kasuje globalnie (foot-gun). | scope delete po rozwiązanej uczelni (lub jawnie udokumentować, że to global-only). |

### 🟡 ŚWIADOMIE ODŁOŻONE (potwierdzone, że nadal istnieją)

**Federacja optymalizacji — globalne delete/update (backlog C, integralność danych).**
Świadomie olane jako *logika federacyjna*, ale to *korupcja danych*:
- `ewaluacja_optymalizacja/tasks/optimization.py:73` (`solve_single_discipline_task`),
  `:536,573` (`optimize_and_unpin_task`), `tasks/reset_pins.py:139` (`reset_all_pins_task`).
- **NOWE instancje tej samej klasy:** `management/commands/solve_uczelnia.py:108`,
  `solve_helpers/persistence.py:28` (`OptimizationRun.filter(dyscyplina).delete()`
  bez uczelni), `views/unpinning_analysis.py:162` (`MetrykaAutora.objects.all().delete()`
  globalny, `Uczelnia.objects.first()`).

**Federacja read-side (świadomie olana lub do decyzji produktowej):**
- `raport_slotow/views/ewaluacja.py:91`, `upowaznienie_pbn.py:90` — listy autorstw
  ewaluacyjnych bez scope po uczelni (model DB-view bez kolumny uczelnia).
- `ewaluacja_common/utils.py:17,33` (`get_lista_prac`) — bez uczelni, ale **dormant**
  (brak żywych callerów, tylko testy).
- `ewaluacja_optymalizuj_publikacje/views.py:320-380` — `MetrykaAutora.get(autor, dyscyplina)`
  bez uczelni → przy >1 uczelni `MultipleObjectsReturned` (HTTP 500, fail-loud).

**pbn_api — lustro danych PBN (decyzja usera: 🟡, udokumentować w komentarzach):**
- `OsobaZInstytucji` (`pbn_integrator/utils/scientists.py:205`, OneToOne `personId`),
  `PublikacjaInstytucji(_V2)` (`mongodb_ops.py:198`, `publications.py:124`),
  `OswiadczenieInstytucji` (`mongodb_ops.py:304`) — write nie taguje FK `uczelnia`
  (nullable, NULL w runtime). Praktycznie OK, bo `uczelnia.pbn_uid` (institution_id)
  jednoznacznie wiąże wiersz z instytucją PBN; brak FK = brak wygody filtrowania,
  nie korupcja. **Działanie: dobre komentarze opisujące to, nie pilny fix.**
- Powiązane globalne delete (kompounduje, ale przy mapowaniu institution_id niegroźne):
  `publication_sync.py:238`, `oswiadczenie_instytucji.py:201` (kasuje `SentData`
  cross-uczelnia — istotne po naprawie #6), `pbn_integrator/utils/statements.py:472`.
- `komparator_pbn_udzialy` (`tasks.py:13`, `utils.py:46,245`) — `porownaj_dyscypliny_pbn_task`
  globalny `.delete()` + iteracja `OswiadczenieInstytucji.objects.all()`; modele wynikowe
  komparatora bez FK uczelnia → 🟡 (federacja-adjacent).

**API REST (`api_v1`) — „API maszynowe, osobny temat" (Audyt 3):**
- `viewsets/struktura.py:11,16` (`Jednostka`/`Wydzial` — jawny FK uczelnia, listowane
  globalnie) — **najmocniejszy kandydat do pull-forward** gdyby API miało być per-uczelnia.
- `viewsets/recent_author_publications.py` — `AllowAny` + CORS `*` + **ignoruje
  `nie_eksportuj_przez_api`/`ukryte_statusy`** (w odróżnieniu od bratnich viewsetów)
  → ortogonalny bug eksportu, niezależny od multi-hosted.
- `viewsets/raport_slotow_uczelnia.py` — per-OWNER (R1, świadomy rozjazd, bezpieczny).
- Globalne listy publikacji/autorów (ciagle/zwarte/doktorska/habilitacyjna/patent +
  `*_Autor`) — atrybuowane tranzytywnie; dane z natury publiczne (bibliografia).

**UI / config / inne:**
- `bpp/multiseek_registry/__init__.py:31` — multiseek base `Rekord.objects.all()`
  (R3a by-design: wyszukiwarka globalna).
- `bpp/multiseek_registry/fields/numeric_fields.py:70-73` — toggle „Index Copernicus"
  per pierwszej uczelni (widoczność pola, nie dane).
- `bpp/tasks.py:36-51` (`_zaktualizuj_liczbe_cytowan`) — pętla per uczelnia OK, ale
  wewnętrzne `klass.objects.all()` nie scope'owane (jawny FIXME: redundancja +
  last-write-wins między WoS-klientami).
- `bpp/admin/core.py:195` (form default `afiliuje` z pierwszej uczelni),
  adminy publikacji bez `SiteFilteredAdminMixin` (changelist cross-uczelnia, superuser
  i tak zwolniony) — design admina.
- Komendy one-off install-specific: `mapuj_kierunki_studiow.py`,
  `fix_pbn_import_oswiadczen_ksiazki.py` (fail-loud).

### ✅ POTWIERDZONE jako poprawne (zbiorczo)

- **Write-side sloty** (`bpp/models/sloty/*`, `cache/punktacja.py`): `ISlot`,
  `IPunktacjaCacher`, `_autorzy_qs` filtrują `jednostka__uczelnia`; CPD tagowane.
- **R1 sloty read-side**: `raport_slotow/views/{autor,uczelnia}.py` przez
  `uczelnia_dla_odczytu`.
- **R2 liczba_n** (`ewaluacja_liczba_n/utils.py`, `views/verify.py`): wszystkie
  delete/create/agregaty z `uczelnia=`; atrybucja `aktualna_jednostka.uczelnia` +
  `skupia_pracownikow`.
- **D metryki** (`ewaluacja_metryki/views/*`, `utils.py`, `tasks.py`): `scope_metryki`,
  `_resolve_uczelnia` single-or-fail, StatusGenerowania per-uczelnia, delete scoped.
- **R3a publiczny**: `nowe_raporty`, `browse` (Lata/Rok), `oai`, `ranking_autorow`
  przez `scope_rekord_do_uczelni` + `tylko_jedna_uczelnia`.
- **R3b pickery**: `units.py`, `simple.py` (Wydzial), `authors.py` przez
  `UczelniaScopedAutocompleteMixin`.
- **PBN push/queue**: `PBN_Export_Queue.uczelnia` + `send_to_pbn` (`entry.uczelnia`);
  downloadery/import/wysyłka-oświadczeń z jawnym `uczelnia_id`+`get_for_pbn_background`;
  B6 `przemapuj_*` taguje uczelnię.
- **B1** `powiazania_autorow/queries.py:_pbn_root` przez `get_for_request`.
- **importer_publikacji** (`ImportSession.uczelnia`), **zbieraj_sloty** CLI
  (single-or-fail), **integrator** matching/klient (delta R2).

---

## Decyzje usera (2026-06-04) — wiążąca klasyfikacja

1. **#1 (punktacja rekordu):** rekord wyszukiwalny wszędzie; tabelka punktacji
   tylko dla `jednostka__uczelnia` oglądającego. → 🔴 naprawić.
2. **#2 (metryki profilu):** pokazać, ale z jednej uczelni — z requestu. → 🔴 naprawić.
3. **#3 (global autocomplete):** jednostki filtrować; autorzy „≥1 jednostka z uczelni";
   rekordy przez `autorzy`. → 🔴 naprawić.
4. **#4 (LataAutocomplete):** jak #3 (przez `autorzy`). → 🔴 naprawić.
5. **#5 (zerowy.py):** „trzeba zrobić, proste" — dokończyć połowiczny fix. → 🔴 naprawić.
6. **SentData:** tagować per-uczelnia (N profili instytucji = N wierszy). → 🔴 naprawić.
7. **OsobaZInstytucji / PublikacjaInstytucji / OswiadczenieInstytucji:** teoretycznie
   per-uczelnia, praktycznie OK (mapowanie `institution_id`) → 🟡 **udokumentować
   w komentarzach**, nie pilny fix.

---

## Podsumowanie liczbowe

- **Klasa 1** (`get_default`): guard szczelny (9 wpisów OK). **NOWE:** druga ślepa
  plamka `Uczelnia.objects.first()` (28×, ~25 w `ewaluacja_optymalizacja` runtime).
- **Klasa 2:** **10 🔴 LUK** do naprawy (wszystkie zweryfikowane osobiście);
  ~20 miejsc 🟡 świadomie odłożonych (federacja optymalizacji, pbn_api lustro,
  API maszynowe, UI/config); rdzeń wątków R1/R2/R3/D/B1–B6 potwierdzony ✅.

---

## STAN REALIZACJI (2026-06-04, po decyzjach usera)

Wszystkie naprawy: TDD (RED→GREEN), invariant single-install, lint czysty.

### ✅ ZROBIONE (9 napraw)
| Track | plik(i) | test |
|---|---|---|
| 2 | `raport_slotow/views/zerowy.py` (+ `…/tests/…/test_raport_slotow_zerowy_per_uczelnia.py`) | 16 ✅ |
| 3a | `oswiadczenia/{views,tasks}.py` (+ `oswiadczenia/test_per_uczelnia.py`) | 18 ✅ |
| 3b | `zglos_publikacje/{forms,views}.py` (+ `…/tests/test_per_uczelnia.py`) | 44 ✅ |
| 5 | `bpp/management/commands/wyczysc_baze.py` — **USUNIĘTA** (nieużywana) | — |
| 7 | `pbn_api/models/{osoba_z_instytucji,publikacja_instytucji,oswiadczenie_instytucji}.py` — komentarze | — |
| 1a | `bpp/views/profile.py` (+ `…/test_views/test_profile_per_uczelnia.py`) | 1 ✅ |
| 1b | `bpp/views/autocomplete/simple.py` `LataAutocomplete` (+ test) | 2 ✅ |
| 1c | `bpp/views/autocomplete/{navigation,search_services}.py` (+ test) | 132 ✅ (autocomplete regr.) |
| 1d | `bpp/models/cache/rekord.py` + `bpp/views/browse.py` (+ test) | 22 ✅ (browse regr.) |

### 📋 SPEC (execution-ready, do wykonania w świeżym kontekście / subagentem)
- **Track 4 — SentData per-uczelnia:** `specs/2026-06-04-sentdata-per-uczelnia-track4-design.md`
  (outward-facing, ~8 call-site'ów spójnościowych + migracja — świadomie NIE
  robione połowicznie na rozciągniętym kontekście).
- **Track 6 — `Uczelnia.objects.first()` sweep + guard:** `specs/2026-06-04-uczelnia-first-sweep-track6-design.md`
  (28 wystąpień; druga ślepa plamka guarda).

### 🟡 Odłożone (bez akcji, odnotowane): federacja optymalizacji (backlog C globalne
delete), API REST maszynowe, pbn_api lustro (Track 7 = komentarze), multiseek by-design.
