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
docker compose up db redis rabbitmq -d

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
(`iplweb/bpp_dbserver`), Redis i RabbitMQ. Dev-owe
`docker compose up db redis rabbitmq` **nie jest wymagane** do
uruchomienia testów i nie koliduje z nimi.

- Wymaganie: działający Docker daemon.
- Plugin wstrzykuje `DJANGO_BPP_DB_PORT`, `DJANGO_BPP_REDIS_PORT`,
  `DJANGO_BPP_RABBITMQ_PORT` (i hosty/hasła) do `os.environ` **przed**
  załadowaniem Django settings, oraz `DJANGO_BPP_SKIP_DOTENV=1`, żeby
  `.env` nie nadpisał wstrzykniętych wartości.
- Wyłączenie (gdy sam odpaliłeś usługi przez docker-compose):
  `BPP_USE_TESTCONTAINERS=0 uv run pytest` lub flag `--no-testcontainers`.
- Reuse kontenerów między runs (znacznie szybciej):
  `BPP_TESTCONTAINERS_REUSE=1`. Domyślnie kontenery są ulotne
  i kasowane przez Ryuk.
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
