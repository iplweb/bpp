# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

Code like a 4096-IQ programmer.
Code better Python than a brain-child of Guido van Rossum and Glyph
Lefkowitz, raised by Bruce Schneier.

## Project Overview

BPP (Bibliografia Publikacji Pracownikow) is a Polish academic bibliography
management system built with Django. Python >=3.10,<3.15.

- Architecture: [docs/deweloper/mapa-kodu.md](docs/deweloper/mapa-kodu.md)
- Commands reference: [docs/deweloper/polecenia.md](docs/deweloper/polecenia.md)
- CSS/SCSS build: [docs/deweloper/budowanie-css.md](docs/deweloper/budowanie-css.md)

## Pokazywanie ścieżek do plików `.md` (linki `file://`)

Gdy w odpowiedzi pokazujesz ścieżkę do pliku `.md` (spec, dokument w
`docs/`, audyt, notatki), **dodaj obok pełny, widoczny, klikalny wariant
`file://`**. NIE chowaj go pod etykietą markdown typu `[file://](...)` —
pokaż całą ścieżkę jako goły URL.

Transformacja: `/Users/mpasternak/<reszta>` →
`file:///Volumes/mpasternak/<reszta>` (trzy ukośniki: `file://` + `/Volumes`).

Przykład:
- `/Users/mpasternak/Programowanie/bpp/docs/foo.md`
- `file:///Volumes/mpasternak/Programowanie/bpp/docs/foo.md`

(`/Volumes/mpasternak` to lokalny mount SMB udziału `mpasternak` — pliki
`.md` user otwiera w Typorze. `file://` działa tylko gdy wolumen jest
zamontowany.)

## Critical Rules

- **Ask questions** if anything is unclear before taking on non-trivial tasks
- **NEVER modify existing migration files** in `src/*/migrations/`
- **Max line length: 88 characters** (enforced by ruff)
- **Worktrees NIGDY w `bpp/` (ani w `.claude/worktrees/`).** Wszystkie
  worktree mają lądować jako siostrzane katalogi obok głównego checkoutu,
  tzn. w `~/Programowanie/`. Nazwa: `bpp-<feature-slug>`.
  - ❌ `bpp/.claude/worktrees/<slug>` — zaśmieca repo, łatwo wpada do `find`,
    `grep`, edytora, snapshotów IDE.
  - ✅ `~/Programowanie/bpp-<slug>` — jako siostra `~/Programowanie/bpp`.
  - Domyślny `EnterWorktree name=<slug>` claude'a tworzy worktree w
    `bpp/.claude/worktrees/` — to **NIE** jest akceptowalne. Zamiast tego:
    ```bash
    git worktree add ~/Programowanie/bpp-<slug> -b worktree-<slug>
    ```
    a potem `EnterWorktree path=~/Programowanie/bpp-<slug>` żeby wejść
    w już-istniejący worktree zamiast tworzyć kolejny.
- **Icons in templates:**
  - Public frontend (Foundation CSS): monochrome Foundation-Icons
    (`<span class="fi-icon"/>`)
  - Django admin (`templates/admin/`): use emoji (no Foundation Icons)
- **Django template comments `{# ... #}` są jedno-liniowe — KAZDA LINIA
  MUSI mieć własne otwarcie `{#` i zamknięcie `#}` na tej samej linii.**
  Po `\n` w środku komentarza parser przestaje go widzieć i tekst wycieka
  do wyrenderowanego HTML-u. Powtarzający się błąd. Reguła:
  - ❌ ZABRONIONE wieloliniowe komentarze typu:
    ```django
    {# linia 1
       linia 2 #}
    ```
  - ✅ ZAWSZE każda linia z osobnym `{# ... #}`:
    ```django
    {# linia 1 #}
    {# linia 2 #}
    ```
  - Alternatywa dla bloków: `{% comment %}...{% endcomment %}` (też OK,
    ale per-line `{# #}` jest preferowane przez użytkownika).

## Python and Django Execution

**ALWAYS use `uv run` prefix for ALL Python commands. NEVER run `python`
directly.**

```bash
# CORRECT:
uv run python src/manage.py shell
uv run pytest src/app_name/tests/

# WRONG - missing uv run:
python src/manage.py shell
pytest src/app_name/tests/
```

## Uruchamianie dev stack-u (preferowane dla agenta)

**Jeśli musisz obejrzeć stronę BPP, uruchomić ją lokalnie albo
sprawdzić jak coś wygląda w przeglądarce — używaj `run-site`,
NIE `docker compose up`.** Dla agenta to znacznie prostsze.

```bash
uv run run-site run
```

`run-site` to zewnętrzny pakiet (`run-site` na PyPI, dawniej wbudowane
`manage.py run_site`). Konfiguracja siedzi w `runsite.toml` w korzeniu
repo. Hooki BPP-specific (PBN token, password_policies cleanup) sa
w `src/django_bpp/runsite_hooks.py`.

Co `run-site run` robi w jednej komendzie:

- startuje PostgreSQL i Redis przez testcontainers (losowe porty,
  bez kolizji z dev-owymi kontenerami `docker compose up db redis`),
- migruje bazę i tworzy superusera `admin`/`admin` (idempotent),
- odpala `runserver` na losowym wolnym porcie (lub `--port`),
- otwiera przeglądarkę z auto-loginem przez `django-dev-helpers`
  (przeskakuje formularz logowania),
- `django-dev-helpers` zapisuje token + porty do gitignored
  dotfile'ów: `.dev_helpers_token`, `.dev_helpers_port`,
  `.dev_helpers_pg_port`, `.dev_helpers_redis_port` — wszystkie
  ulotne, kasowane na exit; patrz sekcja „Autologin dla agentów" niżej,
- `run-site` zapisuje `.run-site-config` (TOML sidecar z connection URLs),
- drukuje w stdout banner z URL-ami + gotowe snippety curl/psql/redis-cli
  dla agenta.

**Dlaczego to lepsze niż `docker compose up` dla agenta:**

- jeden proces zamiast trzech serwisów (web/celery/db) — łatwiej
  uruchamiać w tle, łatwiej wyciągać port z outputu,
- baseline migracji + admin są gotowe od ręki, bez ręcznego
  `migrate`/`createsuperuser`,
- WebFetch / curl działa od strzału dzięki `.dev_helpers_token` +
  `.dev_helpers_port` (agent składa URL bez parsowania bannera/logów);
  `psql`/`redis-cli` analogicznie przez `.dev_helpers_pg_port`
  + `.dev_helpers_redis_port`,
- testcontainers same się sprzątają na exit (Ctrl-C zamyka stack),
- nie wymaga prebuildu obrazu appserver-a (compose by wymagał).

**Najczęściej używane flagi:**

- `--no-browser` — nie otwieraj browsera (zalecane gdy agent uruchamia
  `run-site` w tle przez `run_in_background=true`),
- `--port 8080` — wymuś konkretny port (default: losowy wolny;
  agent najczęściej i tak czyta port z bannera),
- `--reuse` — persystencja kontenerów PG/Redis między uruchomieniami
  (drugi run nie inicjuje od zera; usuń ręcznie kontenery
  `bpp-runsite-pg`/`bpp-runsite-redis` żeby zrestartować),
- `--no-celery` — pomiń celery worker (szybciej, gdy nie testujesz
  background-jobów),
- `--skip-assets` — pomiń `make assets` (gdy CSS/JS jest aktualny),
- `--from-dump PATH` — odtwórz `.sql` / `.sql.gz` / `.dump` zamiast
  baseline.

**Pobranie portu z bannera (gdy run-site w tle):**

```bash
# Po uruchomieniu w tle, port jest w outpucie:
grep -oE 'http://localhost:[0-9]+' /tmp/run_site.log | head -1
```

Domyślny `docker compose up db redis -d` z Quick Reference jest
dla **rzadszych przypadków**: testy z `PYTEST_TESTCONTAINERS_DISABLE=1`
albo gdy potrzebujesz długożyjącej bazy niezależnie od `run-site`.
Do oglądania samej strony — używaj `run-site`.

## Key Commands (Quick Reference)

Full details: [docs/deweloper/polecenia.md](docs/deweloper/polecenia.md)

```bash
# Infrastructure services (when not running locally):
docker compose up db redis -d

# Testing (full suite takes UP TO 10 MINUTES):
uv run pytest
make tests-without-playwright    # fast, no browser tests

# Code quality:
ruff format .
ruff check .
pre-commit                       # NEVER add arguments!

# Frontend:
grunt build                      # after SCSS changes
make assets                      # full frontend build

# Celery:
uv run celery -A django_bpp.tasks inspect registered
```

**Pre-commit rules:** When pre-commit produces issues, analyze output
issue-by-issue. Fix each manually with the Edit tool. Do NOT run
`ruff check --fix` or any automated batch fixes.

## Autologin dla agentów (WebFetch / curl bez logowania)

Gdy user uruchomił `run-site run`, dev stack zapisuje gitignored,
ulotne pliki w korzeniu repo. `django-dev-helpers` (instalowany do
INSTALLED_APPS przez `local.py`) tworzy:

- `.dev_helpers_token` — token autoryzacyjny (chmod 600),
- `.dev_helpers_port` — port runservera (host = zawsze `localhost`),
- `.dev_helpers_pg_port` — port PostgreSQL testcontainera
  (host = zawsze `localhost`, user/pass = `bpp`/`password`,
  baza = `bpp`),
- `.dev_helpers_redis_port` — port Redis testcontainera
  (host = zawsze `localhost`, bez hasła).

`run-site` dodatkowo zapisuje `.run-site-config` (TOML sidecar z
gotowymi connection URL-ami) — uzytkowny gdy chcesz np. `cat
.run-site-config | grep '^url' | tail -1` zamiast skladac URL z paru
dotfile'ow.

Wszystkie istnieją **tylko przez czas życia procesu run-site** i są
kasowane na exit. Jeśli któregoś nie ma — znaczy że dev stack nie
biegnie i nie da się fetchować zalogowanych stron / podpiąć się
do bazy; nie próbuj „obejść" tego logując się przez `/admin/login/`
czy POST-em formularza ani odpalać własnego PG/Redis-a — tylko poproś
usera o uruchomienie `run-site`.

Token uwierzytelnia jako `admin` (superuser) — używaj tylko gdy musisz
zobaczyć stronę wymagającą zalogowania. Do publicznych stron nie ma
sensu, a niepotrzebnie zostawia ślad w `request.user` w logach.

**Pobranie zalogowanej strony przez curl + cookie jar:**

```bash
T=$(cat .dev_helpers_token)
PORT=$(cat .dev_helpers_port)
J=$(mktemp)
curl -sc "$J" -L "http://localhost:$PORT/__autologin__/?token=$T" \
    >/dev/null
curl -sb "$J" "http://localhost:$PORT/<path>"
rm "$J"
```

**Połączenie z bazą PostgreSQL testcontainera (psql, dbshell, etc.):**

```bash
PG_PORT=$(cat .dev_helpers_pg_port)
PGPASSWORD=password psql -h localhost -p "$PG_PORT" -U bpp -d bpp
```

Tej samej kombinacji `host=localhost`, `port=$(cat .dev_helpers_pg_port)`,
`user=bpp`, `password=password`, `dbname=bpp` używaj wszędzie indziej
(SQLAlchemy, pgcli, DataGrip itd.). Nie próbuj odpalać własnego PG —
ten kontener ma już zaimportowany baseline + zmigrowane schema.

**Połączenie z Redis-em testcontainera (redis-cli, debug):**

```bash
REDIS_PORT=$(cat .dev_helpers_redis_port)
redis-cli -p "$REDIS_PORT"
```

**WebFetch tool (Claude Code):** jest bezstanowy — cookie z
auto-loginu nie przeniesie się między kolejnymi wywołaniami.
WebFetcha używaj tylko do publicznych stron. Do zalogowanych
stron użyj snippetu z curl powyżej, ewentualnie spipuj wynik
przez `pandoc -f html -t markdown` jeśli potrzebujesz markdown-a.

**Bezpieczeństwo:** endpoint `/__autologin__/` istnieje tylko gdy
`django-dev-helpers` jest aktywne (INSTALLED_APPS + DJANGO_DEV_HELPERS
dict, lub env var DJANGO_DEV_HELPERS_ENABLED=1 ktory ustawia
`run-site`). Pakiet jest dev-only (extras=dev w pyproject.toml) i
domyslnie no-op w produkcji. Token nie wycieka do gita (gitignore +
ulotny plik). Nie wklejaj zawartości `.dev_helpers_token` do
commitów, do PR-ów, ani do logów które trafią poza maszynę dewelopera.
`.dev_helpers_*_port` zawierają tylko numery portów (nie sekrety) —
można je cytować swobodnie.

## CSS/SCSS Rules

Full details: [docs/deweloper/budowanie-css.md](docs/deweloper/budowanie-css.md)

- **NEVER override Foundation's grid classes** (`medium-4`, `large-12`,
  etc.) in SCSS. Change classes in HTML templates instead.
- After changing SCSS files, run `grunt build`.
- For scroll-to-element, use `window.bpp.scrollToVisible(element)` -
  never `scrollIntoView` alone (sticky headers obscure content).

## Common File Locations

- Main models: `src/bpp/models/`
- Abstract models/mixins: `src/bpp/models/abstract/`
- Admin interfaces: `src/bpp/admin/`
- Admin helpers/mixins: `src/bpp/admin/helpers/`
- API serializers: `src/api_v1/serializers/`
- Context processors: `src/bpp/context_processors/`
- Templates: `templates/` directories in each app
- Static files: `src/*/static/` directories
- Test files: `src/*/tests/` directories or `test_*.py` files
- Management commands: `src/bpp/management/commands/`
- Migrations (including SQL): `src/*/migrations/`
- Frontend assets: `src/bpp/static/` and build via Grunt
- Config: `pytest.ini`, `pyproject.toml`, `package.json`, `Gruntfile.js`
- Generated: `src/bpp/static/500.html` - auto-generated (DO NOT EDIT),
  edit `src/bpp/templates/50x.html` instead

## Static files contract (Docker)

Obraz produkcyjny `iplweb/bpp_appserver` nie generuje staticow na starcie od
zera — robi to w **build stage** i shipuje gotowe pliki, zeby runtime mogl
wystartowac bez `node_modules` (~300+ MB oszczednosci).

Kontrakt miedzy obrazem a deploymentem:

- **Build**: `docker/bpp_base/Dockerfile` (builder stage) robi
  `collectstatic` do `/app/staticroot.baked/`. Katalog jest COPY-owany do
  runtime stage i pozostaje tam jako read-only source of truth.
- **Runtime ENV**: `STATIC_ROOT=/app/staticroot` (default) — ale deployment
  moze to override'owac (np. bpp-deploy ustawia `STATIC_ROOT=/staticroot`
  i mountuje named volume w tym miejscu).
- **Entrypoint** (`docker/appserver/entrypoint-appserver.sh`, Phase 2):
  kopiuje `cp -rf /app/staticroot.baked/. "$STATIC_ROOT/"`. `-f` zawsze
  nadpisuje pliki istniejace w `.baked` (poprzednio bylo `-ru`, ale `-u`
  skipowal kopiowanie gdy mtime na volume byl pozniejszy niz mtime
  `grunt build` w obrazie — typowy przypadek miedzy szybko nastepujacymi
  deployami → stary CSS przezywal restart). Pliki spoza `.baked`
  (tenant-specific custom branding wgrany post-deploy) i tak nie sa
  ruszane, bo cp nie kasuje plikow spoza zrodla. **Runtime nie uruchamia
  `collectstatic`** — wynik bylby dokladnie taki sam jak `.baked` (bez
  `node_modules` YarnFinder zwraca pusta liste, wiec nowych plikow by
  nie znalazl), wiec cp wystarcza.
- **Fallback**: jesli `.baked` nie istnieje w obrazie (stary tag sprzed
  wprowadzenia kontraktu), entrypoint degraduje do tradycyjnego
  `collectstatic` — zachowuje backward compat z obrazami pre-contract.

Deployment (`bpp-deploy`) nie musi nic robic — mountuje named volume na
`$STATIC_ROOT` i nginx go serwuje. Przy upgrade obrazu entrypoint sam
zalewa volume nowymi plikami z `.baked`.

Jesli zmieniasz to: pamietaj ze `.baked` i `$STATIC_ROOT` to DWIE rozne
rzeczy. Do `.baked` (w obrazie) pisze tylko `collectstatic` na buildzie.
Do `$STATIC_ROOT` (volume/katalog runtime) pisze `cp -ru` + runtime
`collectstatic` + ewentualne tenant tooling.

## Docker image publishing (staging-tag + Trivy gate)

Workflow `.github/workflows/build-docker-images.yml` publikuje obrazy
Docker w trzech fazach, zeby skaner bezpieczenstwa mogl faktycznie
zablokowac release zanim kanoniczny tag pojawi sie w rejestrze.

**Dlaczego nie prosty „build → push → scan"?**
Docker Hub nie ma mechanizmu „un-push". Jesli Trivy znajdzie CRITICAL
CVE dopiero po pushu, obraz juz jest publicznie dostepny pod tagiem
wersji (`:2025.12.1`, `:latest`) i deployment moze go pullnac, zanim
ktokolwiek zobaczy raport. Gate po pushu jest dekoracyjny.

**Faza 1 — Build → staging tag**
Bake pushuje do tagu `sha-<short_sha>` (np. `sha-abc1234`). Tag jest
publiczny technicznie, ale niekanoniczny — zadna dokumentacja, zadne
deployment scripty nie referencuja `sha-*`, wiec w praktyce nikt go
nie pullnie.

**Faza 2 — Trivy gate (TYLKO master)**
Skan staging tagu. Polityka:
- **CRITICAL** (z dostepnym fix-em) → hard fail, workflow sie wywala,
  promocja sie NIE wykonuje. Kanoniczny tag wersji nigdy nie powstaje.
- **HIGH** → raport w GitHub Step Summary, nie blokuje. Wiekszosc HIGH
  to szum (DoS w build-time libach, CVE w `wheel`/`jaraco.context`
  z minimalnym realnym impaktem).
- **`--ignore-unfixed`** → pomijamy CVE bez fixa (nic nie da sie z tym
  zrobic).
- Skipowane false-positivy: `autobahn/wamp/cryptosign.py` (przykladowy
  klucz w docstringu), `slapdtest/certs/` (test fixtures python-ldap).

Feature branche NIE sa skanowane — to +3.5 min na pipeline, a ich tagi
sa jawnie tymczasowe (nie release).

**Faza 3 — Promote staging → canonical**
`docker buildx imagetools create -t <canonical> <staging>` kopiuje
manifest w rejestrze. Nie rebuilduje, nie re-pushuje warstw — tylko
zapisuje metadane z referencja do istniejacych layers. ~sek per obraz.
Na master dodatkowo tworzy tag `:latest`.

**Zastrzezenie o rejestrze:**
Raz pushniety digest (nawet pod staging tagiem) zyje w Docker Hub do
momentu recznego DELETE. Staging-tag pattern chroni przed *odkryciem*
zlego obrazu (kanoniczny tag nie powstaje), nie przed jego *istnieniem*.
Dla pelnej izolacji potrzebne bylo by prywatne staging registry +
kopiowanie czystych obrazow do public — niepotrzebne przy obecnej skali.

**Staging tagi akumuluja sie** w Docker Hub jako `sha-*`. Obecnie nie
sa czyszczone — zostaja dla mozliwosci rollbacku po SHA. Jesli lista
staje sie za dluga, dopisz krok DELETE przez Docker Hub API lub cron
usuwajacy tagi starsze niz N dni.

## External Services

### Freshdesk Support
- **Domain**: `iplweb.freshdesk.com`
- **Ticket URL format**: `https://iplweb.freshdesk.com/a/tickets/{ticket_id}`

## Tests

**ALWAYS use pytest conventions - NEVER create unittest.TestCase tests.**

- Standalone functions, no classes (e.g. `test_module_functionality()`)
- Use `@pytest.mark.django_db` for tests using database
- Use `model_bakery.baker.make` for creating database objects
- Fixtures in `src/conftest.py` and subdirectories
- Full suite timeout: at least 600000ms (10 minutes)

### Uruchamiaj testy LOKALNIE — nie spychaj wszystkiego na CI

**Domyślnie odpalaj testy na swojej maszynie.** „Środowiskowo-ciężkie",
„zostawmy to CI", „Playwright wymaga setupu" to NIE są powody, żeby pominąć
lokalny przebieg — to najwyżej powód, żeby najpierw zrobić warunki wstępne
(`make assets`, `make playwright-install`). Brak warunku wstępnego = wykonaj go,
nie pomijaj testu.

- **Praca nad zdalnym branchem / w PR:** odpalenie lokalnego `make tests`
  **równolegle** z czekaniem na CI jest OK i **zalecane** — szybszy feedback,
  łapiesz regresje zanim CI je zwróci, nie marnujesz rundy CI. Te dwa kanały się
  nie wykluczają; rób oba.
- Pełne `make tests` przerywa się na pierwszym błędnym kroku (`make` zwraca na
  Error 1), więc gdy `tests-without-playwright` padnie, kroki
  `tests-only-playwright` i `js-tests` się NIE wykonają. Po naprawie Pythona
  **dokończ** pozostałe kroki (albo ponów całe `make tests`), zamiast uznać je
  za „pominięte".
- Jedyny akceptowalny powód, by czegoś nie odpalić lokalnie: fizyczny brak
  możliwości (np. brak działającego Dockera dla testcontainers) — wtedy powiedz
  to wprost, a nie „jest ciężkie".

### Testy Playwright (`src/integration_tests/`) lokalnie

Testy przeglądarkowe (np. `test_global_search.py`) **da się** odpalić
lokalnie — testcontainery same stawiają PostgreSQL + Redis, a fixture
`channels_live_server` startuje Daphne. Trzeba tylko mieć zbudowany
frontend i przeglądarki Playwright:

```bash
make assets              # zbuduj CSS/JS + .mo — BEZ tego live server
                         # nie wyrenderuje strony i `page.goto` timeoutuje
make playwright-install  # jednorazowo: pobierz przeglądarki Playwright
uv run pytest src/integration_tests/test_global_search.py::test_global_search_user
```

- Pierwszy run bywa wolny (cold start testcontainerów) i `page.goto`
  potrafi raz timeoutnąć — **ponów**, kolejne są szybkie (~2 s/test).
- `--count=N` (pytest-repeat) powtarza test N razy — przydatne do
  łapania timing-flake'ów Playwrighta.
- Żeby pominąć browser-testy w ogóle: `make tests-without-playwright`.

### Testcontainers

Testy używają plugin-ow `pytest-testcontainers` + `pytest-testcontainers-django`
(zewnetrzne pakiety na PyPI; dawniej wewnetrzny `src/testcontainers_bpp/`),
ktore domyślnie startują na losowych portach **własne** kontenery PostgreSQL
(`iplweb/bpp_dbserver`) i Redis. Dev-owe `docker compose up db redis`
**nie jest wymagane** do uruchomienia testów i nie koliduje z nimi.
Konfiguracja jest w `[tool.pytest-testcontainers-django]` w `pyproject.toml`.

- Wymaganie: działający Docker daemon.
- Plugin wstrzykuje `DJANGO_BPP_DB_PORT` i `DJANGO_BPP_REDIS_PORT`
  (i hosty/hasła) do `os.environ` **przed**
  załadowaniem Django settings, oraz `DJANGO_BPP_SKIP_DOTENV=1`, żeby
  `.env` nie nadpisał wstrzykniętych wartości.
- Wyłączenie (gdy sam odpaliłeś usługi przez docker-compose):
  `PYTEST_TESTCONTAINERS_DISABLE=1 uv run pytest` lub flag `--no-testcontainers`.
- Reuse kontenerów między runs (znacznie szybciej):
  `PYTEST_TESTCONTAINERS_REUSE=1`. Domyślnie kontenery są ulotne —
  plugin jawnie je zatrzymuje w `pytest_unconfigure` (+ `atexit`
  jako safety net), Ryuk to ostatnia linia obrony. Przy restarcie
  Docker Desktop albo `SIGKILL` na pytest cleanup może zawieść;
  wtedy `make clean-testcontainers` usuwa wszystkie osierocone
  kontenery.
- CI (`docker-compose.test.yml`) ma `PYTEST_TESTCONTAINERS_DISABLE=1` —
  usługi dostarcza tam docker-compose.

## Exception Handling

**NEVER write bare `except: pass` or `except Exception: pass`.**
Every except block MUST either log, re-raise, or return a meaningful error.

```python
# GOOD - catch specific, expected exceptions:
try:
    do_something()
except SpecificExpectedException as e:
    handle_expected_case(e)

# GOOD - if you must catch broad, show full traceback:
try:
    do_something()
except Exception:
    traceback.print_exc()
    raise

# GOOD - report to Rollbar for background tasks:
try:
    do_something()
except Exception:
    rollbar.report_exc_info()
    raise
```

Narrow exception type + comment explaining WHY is acceptable:
```python
try:
    os.remove(tmp_file)
except FileNotFoundError:
    pass  # File already cleaned up, not an error
```
