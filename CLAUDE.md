# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

Code like a 4096-IQ programmer.
Code better Python than a brain-child of Guido van Rossum and Glyph
Lefkowitz, raised by Bruce Schneier.

## Project Overview

BPP (Bibliografia Publikacji Pracownikow) is a Polish academic bibliography
management system built with Django. Python >=3.10,<3.15.

- Architecture: [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md)
- Commands reference: [docs/COMMANDS.md](docs/COMMANDS.md)
- CSS/SCSS build: [docs/CSS_BUILD.md](docs/CSS_BUILD.md)

## Critical Rules

- **Ask questions** if anything is unclear before taking on non-trivial tasks
- **NEVER modify existing migration files** in `src/*/migrations/`
- **Max line length: 88 characters** (enforced by ruff)
- **Icons in templates:**
  - Public frontend (Foundation CSS): monochrome Foundation-Icons
    (`<span class="fi-icon"/>`)
  - Django admin (`templates/admin/`): use emoji (no Foundation Icons)

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

## Claude Code Web Environment Setup

For cloud sandbox setup instructions, see
[CLAUDE_CLOUD.md](CLAUDE_CLOUD.md).

## Key Commands (Quick Reference)

Full details: [docs/COMMANDS.md](docs/COMMANDS.md)

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

## CSS/SCSS Rules

Full details: [docs/CSS_BUILD.md](docs/CSS_BUILD.md)

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
  kopiuje `cp -ru /app/staticroot.baked/. "$STATIC_ROOT/"`. `-u` (update
  only if newer) nie nadpisuje tenant-specific zmian wgranych do volume
  przez deployment. **Runtime nie uruchamia `collectstatic`** — wynik
  bylby dokladnie taki sam jak `.baked` (bez `node_modules` YarnFinder
  zwraca pusta liste, wiec nowych plikow by nie znalazl), wiec cp wystarcza.
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

### Testcontainers

Testy używają plugin-a `testcontainers_bpp`, który domyślnie startuje
na losowych portach **własne** kontenery PostgreSQL
(`iplweb/bpp_dbserver`) i Redis. Dev-owe
`docker compose up db redis` **nie jest wymagane** do
uruchomienia testów i nie koliduje z nimi.

- Wymaganie: działający Docker daemon.
- Plugin wstrzykuje `DJANGO_BPP_DB_PORT` i `DJANGO_BPP_REDIS_PORT`
  (i hosty/hasła) do `os.environ` **przed**
  załadowaniem Django settings, oraz `DJANGO_BPP_SKIP_DOTENV=1`, żeby
  `.env` nie nadpisał wstrzykniętych wartości.
- Wyłączenie (gdy sam odpaliłeś usługi przez docker-compose):
  `BPP_USE_TESTCONTAINERS=0 uv run pytest` lub flag `--no-testcontainers`.
- Reuse kontenerów między runs (znacznie szybciej):
  `BPP_TESTCONTAINERS_REUSE=1`. Domyślnie kontenery są ulotne —
  plugin jawnie je zatrzymuje w `pytest_unconfigure` (+ `atexit`
  jako safety net), Ryuk to ostatnia linia obrony. Przy restarcie
  Docker Desktop albo `SIGKILL` na pytest cleanup może zawieść;
  wtedy `make clean-testcontainers` usuwa wszystkie osierocone
  kontenery.
- CI (`docker-compose.test.yml`) ma `BPP_USE_TESTCONTAINERS=0` —
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
