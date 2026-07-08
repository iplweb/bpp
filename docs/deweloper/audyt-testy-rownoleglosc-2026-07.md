# Audyt testów pod kątem współbieżności (pytest-xdist / sharding CI / live servery)

Data: 2026-07-08. Zakres: cała suita pytest (testy „zwykłe" + Playwright),
konfiguracja `pytest.ini`, `settings/test.py`→`local.py`→`base.py`, fixtures,
`channels_live_server`, workflow CI (12 shardów). Audyt wykonany czterema
równoległymi skanami: (1) współdzielony stan Redis/channel-layers,
(2) anty-wzorce DB/fixtures, (3) timing/synchronizacja Playwright,
(4) filesystem/porty/env/CI.

## Fakty środowiskowe (rama dla wszystkich znalezisk)

- **PostgreSQL: izolowany per worker.** Każdy worker xdist ma własną bazę
  `test_bpp_gwN` (klon z template). Sekwencje jitterowane losowo
  +50k..500k przy starcie sesji (`src/conftest.py::django_db_setup`).
- **Redis: JEDEN, współdzielony przez wszystkie workery.** Plugin
  `pytest-testcontainers-django` startuje kontenery tylko w kontrolerze
  pytest (workery wykrywają `PYTEST_XDIST_WORKER` i dziedziczą
  `DJANGO_BPP_REDIS_PORT` z env). Na CI analogicznie: jeden Redis per shard
  (`docker-compose.test.yml`), shardy na osobnych VM-kach — brak
  współdzielenia między shardami.
- **Łańcuch settings testowych:** `--ds=django_bpp.settings.test` →
  `test.py` → `from .local import *` → `local.py` → `base.py`. Testy
  dziedziczą **dev-owe** MEDIA_ROOT, cache'e i flagi Celery.
- **Teardown testów transakcyjnych:** monkey-patch
  `TransactionTestCase._fixture_teardown` (`src/conftest.py:92-144`) —
  `flush --allow-cascade`, `reset_sequences=False`, retry z backoffem na
  deadlocki. Nikt nie używa `serialized_rollback`.
- **Daphne (channels_live_server):** session-scoped, jeden subprocess per
  worker, losowy port; konsumenci używają `transactional_db` (TRUNCATE
  między testami); w subprocesie per-request czyszczony jest cache
  ContentType (`src/channels_live_server.py:80-103`).

## Co jest zrobione dobrze (utrzymać)

- Baza per worker + jitter sekwencji (demaskuje testy zależne od małych ID).
- **Channel layers: per-worker prefix `asgi-test-gwN`**
  (`src/django_bpp/channels_prefix.py:35-58`, `base.py:983-991`), spójny
  z pollerem testowym `wait_for_channel_subscription`
  (`src/django_bpp/playwright_util.py:67-76`). Historia nieudanej próby
  i naprawy: `docs/deweloper/testy-channels-broadcast.md`, commit
  `ece1b586b`. Pilnowane testem `src/django_bpp/tests/test_channels_prefix.py`.
- **cacheops rozbrojony w testach** (`settings/test.py:34,45` — usunięcie
  z INSTALLED_APPS + `CACHEOPS_ENABLED=False`, z komentarzem opisującym
  cross-worker leak przez Redis DB 7, który kiedyś powodował 404-ki).
- **Sesje w testach są DB-backed** (nikt poza `production.py`/`auth_server.py`
  nie ustawia `SESSION_ENGINE`) — czyli per-worker Postgres;
  `SESSION_REDIS_*` to martwa konfiguracja.
- Cache domyślny = DummyCache; Redis locks DB 6 — nieużywane w kodzie.
- **Zero stałych portów** w testach (Daphne: port od kernela; testcontainers:
  losowe porty). Zero `networkidle` (w 5 miejscach komentarze, czemu go nie ma).
- **VCR w trybie `none`** (pytest-recording, brak override) — testy nigdy nie
  idą w sieć; reszta HTTP mockowana.
- Login w Playwright przez wstrzyknięcie cookie z `Client.force_login`
  (nie przez UI); session-scoped browser + function-scoped context/page.
- Izolacja shardów CI: świeży checkout, dedykowana VM, własny compose,
  tmpfs na PG, `down -v` na końcu.

---

## Znaleziska KRYTYCZNE

### 1. `MEDIA_ROOT = src/media` — współdzielony, niesprzątany, importowany przez pytest

- `src/django_bpp/settings/local.py:46-49` (dziedziczone przez testy) — stała
  ścieżka w drzewie źródeł, wspólna dla wszystkich workerów.
- W katalogu leży **~1800 wyciekłych plików (~62 MB)**, mnóstwo kopii
  z sufiksami dedupe Django (`test1_*.xlsx`, `conftest_*.py`) — dowód, że
  kolizje między workerami już zachodzą i są maskowane przez
  `FileSystemStorage`.
- Test „zły typ pliku" uploaduje **prawdziwy `conftest.py`**
  (`src/import_dyscyplin/tests/conftest.py:68`, konsumowany przez
  `test_core.py:8` i `test_views.py:35`), który ląduje w
  `src/media/protected/import_dyscyplin/conftest.py` — obok istnieje
  `__pycache__`, czyli pytest faktycznie go zaimportował przy kolekcji.
  Stary uploadowany plik z innej gałęzi może wywalić kolekcję całej suity
  (`ImportError`) albo zdublować fixtures.
- `norecursedirs` w `pytest.ini:53` pilnuje ZŁEJ ścieżki (`src/bpp/media/`,
  a MEDIA_ROOT to `src/media`); `--ignore` też nie zawiera `src/media`.
- Asercje na dokładne nazwy plików / `os.path.exists` po delete
  (`import_dyscyplin/tests/test_models.py:23-36`) działają tylko dzięki
  losowości sufiksów.
- Wzorzec poprawny istnieje w repo:
  `src/zglos_publikacje/tests/test_admin/test_zgloszenie_publikacji.py:13`
  (`settings.MEDIA_ROOT = str(tmp_path)`).

**Fix:** w `settings/test.py` MEDIA_ROOT → tempdir per proces (klucz
`PYTEST_XDIST_WORKER`); `src/media` do `--ignore` i `norecursedirs`;
czystka wyciekłych plików; testy „złego pliku" bez rozszerzenia `.py`.

### 2. Teardown fixture'ów Playwright: TRUNCATE przed zamknięciem przeglądarki

- Wszystkie fixture'y auth-page (`src/fixtures/playwright_fixtures.py:8,39,70,112,138`)
  mają `page` jako PIERWSZY parametr, `transactional_db` jako ostatni.
  Pytest finalizuje w odwrotnej kolejności instancjacji → flush/TRUNCATE
  biegnie, gdy żywa strona wciąż trzyma websocket i może mieć request
  in-flight do sesyjnego Daphne (reconnect WS, redirect po POST, wpis do
  `django_admin_log`) → `ForeignKeyViolation`/deadlock.
- Pasuje do IntegrityError w CI (GitHub Actions run 28946185913) i do
  istnienia retry-loopa na deadlocki w `src/conftest.py:104-141`.
- Testy „toz/tamze" pogarszają sprawę: kończą się w momencie zaobserwowania
  `count()==2` w DB, gdy odpowiedź HTTP / LogEntry / follow-up GET jeszcze
  lecą (`src/bpp/tests/test_playwright/test_admin/test_toz_tamze.py:126-141,
  172-187, 216-234`). `admin_page.wait_for_function("() => true")` to no-op,
  niczego nie synchronizuje.

**Fix:** `transactional_db` jako pierwszy parametr fixture'ów (TRUNCATE po
zamknięciu kontekstu); po klikach zapisujących `page.expect_navigation()` /
`wait_for_url` zanim assertuje się DB; usunąć no-op `wait_for_function`.

### 3. `--only-rerun` wyłącza reruny `@pytest.mark.flaky` dla AssertionError

- `pytest.ini` ma `--only-rerun TimeoutError/TimeoutException/...` BEZ
  globalnego `--reruns`. pytest-rerunfailures stosuje ten filtr RÓWNIEŻ do
  rerunów z markera `@pytest.mark.flaky(reruns=3)`.
- `src/integration_tests/test_bpp_with_notifications.py:116,141` —
  `test_bpp_notifications` failuje przez `AssertionError`
  (`expect().to_contain_text`), która nie pasuje do żadnego wzorca → rerun
  się NIE wykonuje, mimo że komentarz w teście zakłada „0.2^4 combined".
- `test_channels_live_server` (`:96-113`) ma ten sam lossy push WS
  (~20% miss-rate udokumentowany w docs), okno tylko 1000 ms i brak
  markera flaky w ogóle.

**Fix:** dodać `AssertionError` do `--only-rerun` (lub per-marker
`only_rerun=[...]`); ujednolicić testy notyfikacji (marker + timeout).

### 4. Stan bazy per worker jest historia-zależny; `worksteal` czyni historię losową

- Pierwszy test transakcyjny na workerze TRUNCATE-uje dane referencyjne
  istniejące tylko w `baseline.sql` (`bpp_jezyk`, `bpp_charakter_formalny`,
  `bpp_status_korekty`, custom `auth_group`...) — `post_migrate` odtwarza
  tylko contenttypes/permissions/default site. Późniejsze testy czytające
  „ambient data" dostają pustkę:
  `src/importer_publikacji/tests/test_source_form.py:151-153`,
  `test_views_create_publication.py:34-36`
  (`Charakter_Formalny.objects.first()` → None).
- `--timeout 90` (pytest-timeout) może ubić test PO commitach a PRZED
  flushem → osierocone wiersze na resztę sesji workera (z `--reuse-db`
  przeżywają lokalnie do następnej sesji). To psuje globalne asserty:
  `src/integration_tests/test_conftest.py:88-90`
  (`Rekord.objects.all().count() == 1`),
  `src/nowe_raporty/tests/test_seed_raporty.py:23-25`,
  `src/import_dyscyplin/tests/test_models.py:77-140`.

**Fix:** zakaz gołego `.first()`/globalnych count-ów na danych
referencyjnych — zawsze fixture seedujący + count skope'owany do
relacji/PK. Rozważyć `serialized_rollback` albo autouse re-seed po flushu.

---

## Znaleziska ŚREDNIE

### 5. `@pytest.mark.serial` nie daje obiecanej gwarancji

- `src/conftest.py:362-372` mapuje marker na
  `xdist_group("serial_<4-segmenty-ścieżki>")` — serializacja tylko
  WEWNĄTRZ grupy katalogowej. Testy serial z różnych katalogów biegną
  równolegle ze sobą i z niemarkowanymi. Docstring w `pytest.ini`
  („nie może być uruchomiony równolegle z innymi testami") obiecuje więcej.
- Skutek uboczny: wszystkie `src/bpp/tests/test_multiseek_*` lądują w JEDNEJ
  grupie `src_bpp_tests` — bezpieczne, ale psuje balans shardów.

**Fix:** poprawić dokumentację markera ALBO wprowadzić prawdziwą
serializację (dedykowany worker / filelock) dla testów, które jej
naprawdę potrzebują.

### 6. Sprzeczne flagi Celery eager; fallback = współdzielony broker bez konsumenta

- `base.py:362-365` ustawia `CELERY_ALWAYS_EAGER`/`CELERY_TASK_ALWAYS_EAGER`
  = True pod TESTING; `local.py:64` potem bezwarunkowo resetuje
  `CELERY_ALWAYS_EAGER = False`; `settings/test.py` nie przywraca.
  Łaty siedzą późno: `src/fixtures/conftest.py:37-38` (pytest_configure)
  i `src/channels_live_server.py:64` (subprocess Daphne).
- Jeśli rozstrzygnięcie eager kiedykolwiek przechyli się źle, `.delay()`
  cicho publikuje do Redis DB 1 współdzielonego przez wszystkie workery —
  task nigdy się nie wykona (silent no-op zależny od kolejności).

**Fix:** obie flagi jawnie w `settings/test.py`; usunąć późny re-set
z `fixtures/conftest.py`.

### 7. Constance cache (Redis DB 8) bez per-worker KEY_PREFIX — regresja

- Historia: `469507eb1` (Redis-DB-per-worker) → `137fec4df`
  (`KEY_PREFIX = PYTEST_XDIST_WORKER` na aliasie `constance_cache`) →
  **`55e0b1aa6`** (refaktor test/local) USUNĄŁ blok KEY_PREFIX.
  Dziś `local.py:89-99` definiuje `constance_cache` = redis DB 8 bez
  prefiksu, `test.py` nie przywraca.
- Dziś nieszkodliwe: `CONSTANCE_CONFIG = {}` (`base.py:1736`), fixture
  `constance_cache_warmed_up` iteruje pusty dict, nikt nie pisze
  `config.X = ...`. Ale pierwszy nowy klucz constance wskrzesza
  cross-worker leak (worker A cache'uje wartość, worker B ją czyta, choć
  jego własna baza mówi co innego). Ślad ugryzienia:
  `src/bpp/tests/test_models/test_struktura/test_uczelnia.py:31-40`
  lokalnie override'uje `constance_cache` na locmem.

**Fix:** w `settings/test.py` przywrócić KEY_PREFIX per worker albo
przestawić alias na LocMemCache.

### 8. `_clear_caches` w Daphne czyści tylko ContentType — SITE_CACHE przeżywa TRUNCATE

- `src/channels_live_server.py:80-103` czyści per-request wyłącznie
  `ContentType.objects.clear_cache()`. Projekt używa `django.contrib.sites`
  + `get_current_site()` (`src/bpp/admin/uczelnia.py:310-312`,
  `src/bpp_setup_wizard/forms.py:133-135`). Po flushu ID w `django_site`
  się zmieniają, a `SITE_CACHE` w sesyjnym Daphne trzyma stare obiekty →
  sporadyczne 500/`DoesNotExist` zależne od kolejności testów na workerze.
  Ten sam wektor co naprawiony KeyError na ContentType.

**Fix:** dodać `Site.objects.clear_cache()` w `_clear_caches`; przejrzeć
inne module-level cache (dbtemplates, cache Uczelni).

### 9. Mieszanie `admin_page` (Daphne) z `live_server` (WSGI) — dwa serwery per test

- Pliki: `src/bpp/tests/test_admin/test_crossref_api_sync_playwright.py:34-37`,
  `test_toz_tamze.py` (wszystkie), `test_wydawnictwo_autor.py`,
  `test_autor_inline_wydawnictwo.py`, `test_oswiadczenie_ken.py`,
  `test_clarivate.py`, `test_wydawnictwo_ciagle.py`,
  `src/raport_slotow/tests/test_playwright/test_raport_slotow_autor/test_form.py`.
- `admin_page` stawia Daphne, a test nawiguje na `live_server` —
  podwójna presja na zasoby (dokładnie ta, którą docstring
  `channels_live_server.py:185-191` wskazuje jako źródło kaskadowych
  timeoutów `page.goto`), plus WSGI serwer nie ma per-request czyszczenia
  ContentType/Site.

**Fix:** nawigować na `channels_live_server.url` (już wstrzyknięty).

**UZUPEŁNIENIE (po wdrożeniu):** przełączenie NIE jest bezwarunkowe.
Kryterium wyboru serwera:

- `channels_live_server` (Daphne, **subprocess**) — domyślnie; wymagany
  dla WebSocket/notyfikacji.
- `live_server` (WSGI, **wątek w procesie testu**) — WYMAGANY, gdy test
  opiera się na stanie żyjącym tylko w procesie testu: `mocker.patch` /
  `monkeypatch` na kodzie serwerowym (np. `test_clarivate.py` patchuje
  `Uczelnia.wosclient`), fixture `settings` pytest-django (np.
  `test_oswiadczenie_ken.py` zmienia `BPP_POKAZUJ_OSWIADCZENIE_KEN`),
  kasety VCR dla server-side HTTP (np.
  `test_crossref_api_sync_playwright.py` — widok „pobierz z crossref"
  woła api.crossref.org). Subprocess Daphne ma własną kopię settings
  i nie widzi monkeypatchy — test z Daphne wykonuje PRAWDZIWY kod
  (albo idzie w prawdziwą sieć) zamiast mocka.

Pliki wymagające `live_server` mają komentarz „UWAGA: celowo
live_server" przy fiksturach.

### 10. Wyścigi we wzorcach fixture'owych `get_or_create`

- `pbn_dyscyplina2` (`src/conftest.py:390-399`): `uuid=uuid4()` w LOOKUPIE
  (nie w defaults) — `Discipline` nie ma unique na `code`, więc każde
  wywołanie INSERT-uje nowy wiersz `code="202"` → `MultipleObjectsReturned`
  w kodzie produkcyjnym (`import_common/core/dyscyplina.py:59,64,79`,
  `pbn_integrator/utils/dictionaries.py:155`). `pbn_dyscyplina1` robi to
  dobrze (uuid w defaults).
- `pbn_discipline_group` (`src/conftest.py:402-416`): klucz zawiera
  `validityDateFrom=today-7d` — leftover z sesji rozpoczętej wczoraj
  (reuse-db + crash) już nie matchuje → drugi group → dyscypliny
  rozszczepione między grupy; fallback `.first()` bez `order_by`.
- `jezyki`/`tytuly`/`charaktery_formalne`
  (`src/fixtures/conftest_system.py:63-90`) + `bpp/tests/util.py:152`:
  `get_or_create(pk=1, skrot=...)` — pk I klucz naturalny razem w lookupie;
  gdy wiersz o tym samym skrocie istnieje pod innym pk → INSERT →
  IntegrityError. Działa tylko dzięki sprzężeniu z zawartością baseline'u
  (`assert pl.pk == 1`).

**Fix:** uuid do defaults; stały klucz naturalny bez daty bieżącej;
lookup po kluczu naturalnym, nigdy po pk; usunąć `assert pl.pk == 1`.

### 11. `content_type_id=1` na sztywno

- `src/bpp/tests/test_tasks.py:48-49` — po pierwszym flushu na workerze
  content types odtwarzają się na zjitterowanych sekwencjach →
  `ForeignKeyViolation` zależny od kolejności worksteal.

**Fix:** `ContentType.objects.get_for_model(...)` (dobry wzorzec:
`pbn_wysylka_oswiadczen/tests/test_views.py:308`).

### 12. `PYTEST_TESTCONTAINERS_REUSE=1`: dwie sesje pytest na jednym hoście kolidują

- Stałe nazwy kontenerów `bpp-tc-*` + stałe nazwy baz `test_bpp_gwN` —
  dwie równoległe sesje (człowiek + agent, dwa worktree) robią sobie
  nawzajem TRUNCATE.

**Fix:** udokumentować „jedna sesja reuse per host" albo kluczyć nazwy
po ścieżce checkoutu.

---

## Znaleziska POMNIEJSZE

- **Sleepy jako synchronizacja pusha WS**:
  `test_bpp_with_notifications.py:129,137,157,160` (2 s + 1 s per test);
  `:72` — `time.sleep(1)` po `form.submit()` w teście webtestowym (eager
  = synchroniczne; sleep nic nie robi). Docelowo: deterministyczne ACK
  doręczenia zamiast buforów.
- **`click` + `wait_for_load_state("domcontentloaded")` = race** (wraca
  natychmiast na STAREJ stronie): `test_wydawnictwo_autor.py:73-76`,
  `test_toz_tamze.py:89-96`, `test_wydawnictwo_zwarte.py:49-50`.
  → `expect_navigation()` albo `expect(...).to_contain_text(...)`.
- **`time.sleep`-polling blokujący event loop Playwrighta**:
  `test_crossref_api_sync_playwright.py:12-19`, `test_toz_tamze.py:14-21`.
  Poprawny wzorzec już jest w `test_clarivate.py:16-18`
  (`page.wait_for_timeout` w pętli deadline).
- **`locator.count() == 3` bez auto-waita**: `test_embed_widget.py:38-41`
  → `expect(...).to_have_count(3)`.
- **Czas**: `CURRENT_YEAR = datetime.now().year` zamrożony przy imporcie
  (`bpp/tests/util.py:129`) vs `rok` fixture liczony w call-time;
  `test_multiseek_basic.py:139` assertuje `str(datetime.now().date())` —
  flake o północy. → time_machine/freezegun albo jedno źródło zegara.
- **`test_google_analytics.py:20-31,44-53`** — ręczna mutacja settings
  z try/finally zamiast fixture'a `settings` (jedyny prawdziwy przypadek;
  pozostałe ~40 hitów używa fixture'a poprawnie).
- **`Cookielaw.accept()` bez guarda w fixture'ach**
  (`playwright_fixtures.py:91,160`) — jeśli skrypt nie zdąży się
  załadować, cały test pada na setupie.
- **Martwy finalizer** `normal_django_user`
  (`src/fixtures/conftest_browser.py:28-31`) — `fin()` zdefiniowane,
  nigdy nie zarejestrowane.
- **`test_smoke.py:140-201`** — rekurencyjny crawler z `except: pass`,
  najdłuższy kandydat na timeout-kill; limit stron/czasu + marker slow.
- **Budżet czasu**: `--timeout 90` vs pojedyncze waity po 30 s
  (`test_podpowiedzi_dyscyplin.py:36-38`, `test_smoke.py:168`) — trzy
  wolne kroki = pytest-timeout ubija test w środku wywołania Playwrighta,
  co potrafi zostawić zombie-context psujący kolejne testy.
- **Brak `--tracing retain-on-failure`** — debugowanie flaków CI opiera
  się na ręcznych dumpach `page.content()` (`test_global_search.py:105-110`).
- **`refresh_sitemap`** pisze do `src/django_bpp/staticroot`
  (`test_sitemaps.py:25`, dziś xfail) + `STATICSITEMAPS_ROOT_DIR` liczony
  z `os.getcwd()` przy imporcie (`base.py:1516`).
- **`NamedTemporaryFile(delete=False)`** w `src/oswiadczenia/tasks.py:523` —
  leak pliku przy wyjątku (unikalne nazwy, tylko śmiecenie).
- **`.test_durations`**: `tests-without-playwright` i `tests-only-playwright`
  oba mergują plik — nie odpalać dwóch duration-storing suitów naraz
  w jednym checkoucie.
- **`import_pracownikow` `Autor.objects.get(pk=50)`**
  (`tests/test_models/test_models.py:26,36`) — pk zaszyty w XLSX fixture;
  odporny na jitter (explicit-pk insert), kruchy na zmianę pliku.
- **Znany in-worker flake pusha channels** (~20% miss między `group_send`
  a handlerem konsumenta) — udokumentowany w
  `docs/deweloper/testy-channels-broadcast.md`; NIE jest cross-worker,
  przeżywa nawet z prefiksem per worker. Wymaga naprawy przyczynowej
  w warstwie channels, nie w testach.

---

## Plan działań (priorytety)

1. **MEDIA_ROOT → tmp per worker** w `settings/test.py` + `src/media` do
   `--ignore`/`norecursedirs` + czystka katalogu + test „złego pliku" bez
   `.py`. (usuwa całą klasę kolizji plikowych i ryzyko importu obcego
   conftest)
2. **Kolejność parametrów fixture'ów Playwright** (`transactional_db`
   przed `page`) + `expect_navigation` w toz/tamze + usunięcie no-op
   `wait_for_function("() => true")`. (prawdopodobna przyczyna
   IntegrityError z CI run 28946185913)
3. **`AssertionError` do `--only-rerun`** + marker flaky dla
   `test_channels_live_server`. (odzyskuje reruny, na które testy już liczą)
4. **Jednoznaczne flagi Celery eager + KEY_PREFIX constance**
   w `settings/test.py`.
5. **`Site.objects.clear_cache()`** w `_clear_caches` Daphne.
6. Dalej, stopniowo: fixture'y get_or_create (pkt 10), `content_type_id=1`
   (pkt 11), globalne count-y (pkt 4), sleepy WS, semantyka markera
   `serial` (pkt 5), tracing retain-on-failure.
