# Plan ekstrakcji kodu PBN → `pbn-client` / `django-pbn-client`

Status: **w toku**. Dokument roboczy.
Wersja 4 — po piątej opinii (Fable + Codex, read-only) (2026-07-14).

## 0. Architektura docelowa i stan

**Decyzja: żadnego przejściowego `packages/`.** Paczki na PyPI, BPP konsumuje
je jak każdą zależność.

```
PyPI: pbn-client, django-pbn-client   ← JEDYNE źródło
   iplweb/bpp (gałąź)  ← usuwa packages/, zależy od paczek z PyPI
```

Stan: obie **opublikowane 0.1.0**, repo publiczne `github.com/iplweb/*`, tag
`v0.1.0`, Trusted Publishing gotowy. Repo zewnętrzne = kanoniczne. `packages/`
w monolicie = do usunięcia.

**Zweryfikowane (Fable, diff sdist↔`packages/`):** PyPI 0.1.0 ≡ `packages/` z
dokładnością do docstringów + JEDNEGO stringa runtime (`auth.py:59`
„konfiguracji aplikacji" vs „Uczelnia"); żaden test BPP nie asertuje treści →
**przepięcie jest behavior-safe**. (UX: użytkownik BPP traci podpowiedź o
obiekcie Uczelnia — rozważyć przewinięcie komunikatu po stronie BPP.)

Podstawa: audyt wewnętrzny + 5 niezależnych opinii. **Werdykt najnowszej pary
(Fable/Codex): plan merytorycznie trafny, ale NIE gotowy do wykonania jak
napisany** — patrz blockery niżej.

## 1. Zasady (guardrails)

1. Test couplingu; app-glue zostaje w BPP; `django-pbn-client` = turnkey
   DOWNLOADER, nie SCHEMA (jak v3).
2. **Wydania są WAVE'ami, nie pojedynczymi paczkami** (Codex, blocker). Zmiana
   dotykająca kontraktu `pbn-client`↔`django-pbn-client` (np. P2) wymusza
   **równoczesne** wydanie OBU paczek + bump obu w BPP atomowo. Nie da się wydać
   `pbn-client 0.2` w oderwaniu, bo `django-pbn-client 0.1` pinuje `pbn-client<0.2`.
3. **Cleanup API (§5) wchodzi w to samo wydanie 0.2**, z aliasami — nie „po 0.2".
4. Każdy shim: stary import, nowy import, tożsamość klasy (`alias is Klasa`),
   wersja usunięcia — udokumentowane.
5. Bugi się naprawia/usuwa, nie ekstrahuje.

---

## 2. Faza 0 — bugfixy (do `bpp` `dev`)

### B0a — 422 „publication not found" rzuca `TypeError` ✅ potwierdzone (oba)
- `BrakIDPracyPoStroniePBN(HttpException)` (`exceptions.py:78`) dziedziczy
  `__init__(status_code,url,content)`; call-site `publications.py:362` woła z
  jednym argumentem → `TypeError`.
- Fix: `BrakIDPracyPoStroniePBN(e.status_code, e.url, e.content)`.
- **Edge (Codex):** `smart_content` może zwrócić `bytes` po błędzie dekodowania
  → test `f"..." in e.content` sam rzuci `TypeError` PRZED raise (`utils.py:18`,
  `publications.py:357-360`). Naprawić też membership-test (bytes-safe).
  Testy: 404 / 422-match / 422-nomatch / content=bytes. Nakład: **S**.

### B0b — stored-XSS w renderowaniu błędów PBN w kolejce ⚠️ SZERSZE (oba) [HIGH]
Realny, PRODUKCYJNY XSS (nie martwy `format_json`):
- `pbn_export_queue/templatetags/pbn_queue_extras.py` — `format_pbn_error`
  interpoluje surowe dane PBN do `mark_safe` w ~10 sinkach (opisane w review),
  używane w `pbn_export_queue_table.html:133`.
- `pbn_export_queue_detail.html:466-485,507-510` — `msg.content|safe`,
  `komunikat|safe` (surowe traceback z ciałem odpowiedzi PBN).
- `pbn_export_queue/admin.py:41-44,92-94` — widget renderuje każdy TextField
  jako zaufany HTML.
- Fix: escapować dane PBN przed `mark_safe`/usunąć `|safe`; przepisać
  `test_template_filters.py`. Martwy `format_json` — usunąć (nie ekstrahować).
  Nakład: **S→M**.

### B0c — usuń martwy legacy słownika dyscyplin ✅ (oba)
`integruj_dyscypliny`/`_ensure_discipline_groups` (`dictionaries.py:105-181`)
wołają nieistniejący `get_discipline_groups()`, zero produkcyjnych call-site
(tylko testy). Usunąć + testy. NIE wymyślać endpointu. Nakład: **M**.

### B0d — podwójny `download_disciplines()` przed `sync_disciplines()` ✅ (oba)
`sync_disciplines` samo woła `download_disciplines` (`disciplines.py:48`);
call-site `pbn_integrator.py:181-182`, `initial_setup.py:81-82`. Zaktualizować
`test_initial_setup.py:41` (`assert_called_once`). Nakład: **S**.

---

## 3. Faza 1 — `pbn-client` (wave 0.2)

### P1 — identyfikatory PBN — niskie
`check_mongoId` (`validators.py:1`) + regex UID/URL (`providers/pbn.py:14,233`)
→ `pbn_client.identifiers`. 1 konsument `check_mongoId`. Nakład: **S**.

### P2 — `simple_page_getter` → `pbn-client` jako REDESIGN + WAVE ⚠️
- Redesign: skończona `RetryPolicy` + backoff; skip tylko celowych statusów;
  jawne raportowanie pominiętych stron. Retry ma żyć **w iteratorze stron
  pbn-client** (nie w D4). Uwaga: transport ma już własny retry
  (`transport.py` `max_retries=15`) — zdefiniować interakcję dwóch warstw.
- **Live defect (Fable): to nie nieskończony retry** (`repeat_on_failure=True`
  ma zero produkcyjnych konsumentów), tylko **ciche pomijanie 401/403** przy
  `skip_page_on_failure=True` (jedyny call-site
  `pbn_weryfikuj_profil_instytucji.py:23`).
- **WAVE (Codex/Fable):** `simple_page_getter` to opublikowane API
  `django-pbn-client 0.1` → przeniesienie wymusza wydanie **django-pbn-client
  0.2** równocześnie: re-export shim w `django_pbn_client.pages` + bump pinu
  `pbn-client>=0.2`. Określić, która paczka trzyma shim (obie: pbn-client daje
  implementację, django-pbn-client re-eksportuje). Nakład: **M**.

### P3 — `PublicationNotFound(HttpException)` — po B0a ⚠️ warstwa + 404
- **Rozpoznanie RAZ w endpoincie paczki** (`mixins/publications.py:22`), nie w
  2 call-site BPP — inaczej zewnętrzni konsumenci nie dostają wyjątku.
- Alias `BrakIDPracyPoStroniePBN = PublicationNotFound` (**przypisanie, ta sama
  klasa**, `is`), nie podklasa. Trzymać oddzielnie od `BPPPublicationNotFound`
  (inne znaczenie: brak rekordu BPP, `exceptions.py:149`).
- **Decyzja 404 (Codex):** rozszerzenie 422→404 zmienia zachowanie istniejących
  handlerów — jeden **kasuje lokalny cache PBN** (`odswiez_tabele_publikacji.py:23`),
  inny zwraca przyjazny per-item fail (`publications.py:419`). Wymaga jawnej
  decyzji + testów regresji. Lockstep call-site: `providers/pbn.py:255`,
  `publications.py:355,419`, `odswiez_tabele_publikacji.py:23`. Nakład: **M**.

### P4 — kontrakt błędów: `ErrorRecord` + reader-first (stages) ⚠️ ROZBUDOWANE
- `HttpException.as_dict()` — **tylko jeśli `str()` bez zmian** (testy paczki
  zależą od tuple-repr, `test_pbn_validation_error.py:75`).
- Format persystencji: wersjonowany `ErrorRecord` — ale (Codex) writer łapie też
  **dowolne** wyjątki, a legacy manager przyjmuje dowolny `exception` → „3
  formaty" to hipoteza, nie inwariant. Schemat musi mieć: wariant generic
  `message`, **nullable pola HTTP**, jawny **dyskryminator**, zachowanie dla
  malformed/unknown-version, limity rozmiaru przed serializacją; osobno bound
  `api_response_status` (`sentdata.py:246`). Writerzy: `publication_sync.py:218`,
  `sentdata.py:97,231`. Parsery: `views/utils.py`, `pbn_queue_extras.py:191`,
  `admin/sentdata.py:91`.
- **Rollout = osobne DEPLOYY, nie kolejność operacji (Codex):** (1) deploy
  reader (JSON + legacy tuple + traceback), (2) restart floty, (3) deploy writer,
  (4) później usunięcie legacy wg telemetrii/backfill. `SentData.exception`
  (tuple) i queue `komunikat` (traceback) to **dwa różne** store'y — wersjonować
  osobno. Nakład: **L**.

### A3 — normalizacja autora ⚠️ SEMANTYCZNE SCALENIE, nie dedup (oba)
`publication.py:104` (`lastName`; `firstName or givenNames or name`; obsługuje
non-dict) vs `pbn_importuj_uid.py:90` (`familyName or lastName`; `givenNames or
name`; zakłada dict). Scalenie mechaniczne **zmienia zachowanie**. Potrzebna
**semantyka unii** + charakteryzacja obu ścieżek. Albo odłożyć. Nakład: **M**.

---

## 4. Faza 2 — `django-pbn-client` (wave 0.2+)

### D2 — `get_or_download(model, id, fetch)` ⚠️ uwzględnić istniejący helper (Codex)
- Trzy `ensure_*` (`mongodb_ops.py:46`) zwracają `None`; **ale** istnieje już
  `get_or_download_publication` (`importer/helpers.py:552`), który **zwraca
  instancję** — model docelowy API. Ujednolicić, nie tworzyć trzeciego.
- Doprecyzowanie: zwraca instancję; **bez HTTP w długiej transakcji**; nie
  przejmuje polityki błędów BPP. Konsumenci: `importer/__init__.py:96`,
  `importer/books.py:50`, `pbn_importuj_uid.py:55` + call-site `ensure_*`. Nakład: **S→M**.

### D4 — downloader wysokiego poziomu jako CIENKA FASADA ⚠️ przeprojektowane (oba)
- **Duplikuje istniejące:** sekwencyjny ≈ `download_pbn_objects`
  (`persistence.py:100`), współbieżny ≈ `download_pages`+`ThreadedModelSaver`
  (`pages.py:132,72`). D4 = **fasada** nad nimi (nie trzecie wejście); mapa na
  istniejące `method`/`workers`.
- **Retry page-0 (Codex, blocker):** konstrukcja `PageableResource` już pobiera
  stronę 0 → `download_to_model(resource, retry_policy=…)` nigdy nie ponowi
  pierwszej strony. Wymaga **fabryki resource** (callable) albo retry w
  iteratorze pbn-client (P2).
- **Liczniki:** `upsert_pbn_object` zwraca instancję dla create/update/no-op →
  `saved/skipped/errored` niedefiniowalne bez zmiany API; wątki → akumulacja
  thread-safe; tryb `processes` (fork) → liczniki przez IPC. Dodać typed outcome.
- **Musi przyjmować `client`** (istniejący sekwencyjny saver i BPP-owe threaded
  savery tego wymagają, `publications.py:41`).
- **Cel charakteryzacji/migracji:** `pbn_pobierz_publikacje_z_instytucji_v2.py`
  już robi sequential/threaded + continue-on-error + progress + liczniki — ALE
  jego page-fail ustawia `success=False`, a callery liczą tylko processed/
  success/error → błędy stron **znikają** z sumy; D4 **nie kopiować** tego.
- Nakład: cienka fasada **M**; pełne liczniki+retry+processes **L**.

### D3 — sync słowników (język/kraj/dyscypliny) — po B0c ⚠️ transakcja + tożsamość (Codex)
- Rdzeń „pobierz → upsert do wstrzykniętego modelu": języki + **kraje**
  (`dictionaries.py:85`) + dyscypliny (payload grupowy `disciplines.py:17`).
  Matching do `Jezyk`/`Dyscyplina_Naukowa`/`TlumaczDyscyplin` zostaje w BPP.
- **Materializować odpowiedź PRZED `transaction.atomic`** (obecny downloader
  otwiera transakcję przed remote call). Kontrakty tożsamości per słownik:
  język/kraj = `code`; dyscypliny = `(parent_group, uuid)` + tworzenie grup.
  Buduje tylko na aktualnym payloadzie (legacy usunięty w B0c). Nakład: **M**.

### D1 — toolkit admina ⚠️ ZAWĘŻONE/ODŁOŻONE (jak v3)
Tylko `BaseMongoDBAdmin` + **bezpieczne** widgety, jako `django_pbn_client.admin`
bez re-exportu z `__init__`. NIE publikować martwych/niebezpiecznych helperów
(`format_json` → B0b). Pułapki: wildcard `admin/__init__.py`, `filters.py`
importuje `bpp`, 13 plików, import mieszany. Priorytet **niski**.

### A2 — marker `[❌ USUNIĘTY]` → helper na `BasePBNMongoDBModel` — ~zero
6 modeli, `status` już na bazie (`models.py:25`). Nakład: **S**.

---

## 5. Cleanup publicznego API — w WAVE 0.2 (z aliasami)

- `StatementsResendFailedException(publication_pk,…)` → `correlation_id`
  (+ property/alias `publication_pk`).
- `SciencistDoesNotExist` → `ScientistDoesNotExist` + alias (ta sama klasa).
- Przegląd całego publicznego API przed 0.2. Musi być **w tym samym wydaniu**
  co reszta 0.2 (Codex: nie „po 0.2").

---

## 6. Odłożone

Normalizacja payloadów publikacji (różne fallbacki — nie łączyć); abstrakcyjne
modele encji / `ModelRegistry` / persystery relacji (contract-risk). Stary kod
offline/multiprocessing → konsolidacja/usunięcie.

---

## 7. Kolejność wykonania (poprawiona)

1. **Przepięcie BPP na PyPI (krok 1) — ROZSZERZONA checklista:**
   usuń `packages/` + `[tool.uv.workspace]`/`sources`; **usuń 4× `COPY packages/`
   z `docker/bpp_base/Dockerfile` (62-72, 240-245, 397-403, 464-469)**;
   `pytest.ini` `testpaths = src`; `.dockerignore:68`; dodaj deps PyPI; `uv sync`;
   weryfikacja `pytest` + `manage.py check` + `makemigrations --check` +
   **build obrazu produkcyjnego i test-runnera** (pytest/check tego nie łapią).
   PR do `dev`.
2. **Faza 0**: B0a → B0b → B0c → B0d (PR-y do `dev`).
3. **Wave 0.2** (atomowo, oba pakiety + cleanup §5): P1, P2(redesign), P5,
   P3(po B0a), A3; D2, A2; **oba wydania naraz** → bump obu w BPP.
4. **P4** (ErrorRecord + reader-first jako osobne deploye).
5. **D4** (cienka fasada) → **D3**(po B0c).
6. D1 zawężone lub dalej odłożone.
7. Odłożone.

Uwaga: wcześniejsze fałszywe tezy planu skorygowane — **P5 „zero testów" jest
nieprawdą** (jest test integracyjny `test_pbn_test_wysylka_interaktywna.py:385`
+ unit `test_client_sync.py:905`); zakres P5 = faktyczna nieobsłużona macierz
edge-case, nie „brak testów".
