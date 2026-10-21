# Commands Reference

For detailed architecture, see [mapa-kodu.md](mapa-kodu.md).

## Development Commands

**The development server (appserver) runs through docker-compose** and automatically
restarts when code changes are detected. Never run `manage.py runserver` directly.

```bash
# Check if the server is running:
nc -zv localhost 8000

# View server logs:
docker-compose logs -f appserver

# Start infrastructure services (PostgreSQL, Redis):
docker compose up db redis -d
```

- `uv run python src/manage.py migrate` - Apply database migrations
- `uv run python src/manage.py shell` - Django shell
- `uv run bpp-manage.py` - Alternative management command entry point

## Playwright Testing Setup

**Admin credentials for Playwright tests:**
- Username: `admin`
- Password: `foobar123`
- Reset script: `bin/ustaw-domyslne-haslo-admina.sh`

If login fails during Playwright tests, reset the admin password first:
```bash
bin/ustaw-domyslne-haslo-admina.sh
```
Note: The script requires `expect` to be installed on the system.

## Frontend Build Commands

- `yarn install` - Install Node.js dependencies
- `grunt build` - Build frontend assets using Grunt
- `make assets` - Run both yarn install and grunt build and Django collectstatic

## Testing Commands

- `uv run pytest` - **PRIMARY COMMAND** - Run all tests (configured in pytest.ini)
- `uv run pytest src/app_name/` - Run tests for specific app
- `uv run pytest src/app_name/tests/test_file.py` - Run specific test file
- `uv run pytest src/app_name/tests/test_file.py::test_function_name` - Run specific test
- `uv run pytest -k "test_pattern"` - Run tests matching pattern
- `uv run pytest -v` - Verbose output
- `uv run pytest --ds=django_bpp.settings.local` - Specific Django settings (rarely needed)

**Alternative make commands (internally use `uv run pytest`):**
- `make tests-without-playwright` - Tests excluding Playwright with parallelization (fast)
- `make tests-only-playwright` - Only Playwright tests with parallelization (slow)
- `make tests` - Full test suite
- `make full-tests` - Complete test suite

**Test execution notes:**
- Full test suite takes **UP TO 10 MINUTES** - never use timeout restrictions
- Tests use `--reuse-db` option by default for faster execution
- Tests automatically rerun on TimeoutError, ElementClickInterceptedException,
  ElementDoesNotExist, and TimeoutException
- Default Django settings: `django_bpp.settings.local` (configured in pytest.ini)
- Test fixtures available in `src/conftest.py` and subdirectories

## Celery Commands

- `uv run celery -A django_bpp.tasks` always, for example:
  `uv run celery -A django_bpp.tasks inspect registered`

## Code Quality Commands

- `ruff format .` - Format Python code
- `ruff check .` - Lint Python code and check import sorting
- `ruff check --fix .` - Auto-fix linting issues where possible

**Pre-commit:**
- `pre-commit` - Run pre-commit hooks (**NEVER add arguments like --all-files**)
- When pre-commit produces issues: analyze output issue-by-issue, fix each manually
  with the Edit tool. Do NOT run `ruff check --fix` or any automated batch fixes.

## Maintenance Commands

- `make clean` - Clean build artifacts and cache files
- `make distclean` - Deep clean including node_modules and staticroot
- `bumpver bump` - Bump version (configured in pyproject.toml)
- `make destroy-test-databases` - Remove all test databases
- `make js-tests` - Run JavaScript/QUnit tests
- `make docker` - Build all Docker containers
- `make bdist_wheel` - Build distribution wheel for production
- `make generate-500-page` - Generate static 500.html page (auto-generated, DO NOT EDIT)
  - `src/bpp/static/500.html` is auto-generated from `src/bpp/templates/50x.html`
  - To modify the error page, edit `src/bpp/templates/50x.html` and run
    `make generate-500-page`

## Git Worktree Setup

```bash
git worktree add -b feature/my-feature ../bpp-feature dev
cd ../bpp-feature
```

Worktree działa out-of-the-box — testy używają `testcontainers_bpp`
(własne kontenery na losowych portach), więc nie potrzebują
`docker compose up db redis`. Jeśli chcesz uruchomić dev-server
w worktree, pamiętaj że porty 5432/6379/8000 są współdzielone z
innymi worktree — odpalaj dev-stack tylko w jednym na raz.

## Testowanie pull requestów

Do ręcznego przeklikania PR-a z GitHuba (cudzego albo własnego z innej
maszyny) nie przełączaj gałęzi w głównym checkoucie — użyj:

```bash
make pr PR=856                      # pobierz PR, przygotuj worktree, uruchom run-site
make pr PR=856 ARGS="--no-celery"   # dodatkowe flagi dla `run-site run`
make pr PR=856 DUMP=example         # na najnowszym backupie z ~/Backups/*example*/
make pr PR=856 DUMP=~/x.sql.gz      # ... albo na konkretnym pliku dumpa
make pr PR=856 DUMP=none            # goła baza mimo ustawionego BPP_PR_DUMP
make pr PR=856 NO_RUN=1             # tylko przygotuj worktree, bez run-site
make pr-list                        # worktree PR-ów, backupy do DUMP=, otwarte PR-y
make pr-clean PR=856                # usuń worktree i gałąź pr-856 [FORCE=1]
```

Co robi `make pr` (`bin/pr-worktree.sh`):

1. `git fetch origin pull/<N>/head` — działa też dla PR-ów z forków.
2. Tworzy worktree `~/Programowanie/bpp-pr-<N>` na gałęzi `pr-<N>`
   (siostra głównego checkoutu, zgodnie z regułą o worktree). Gdy worktree
   już istnieje, resetuje go do najnowszego commita PR-a — czyli ponowne
   `make pr PR=<N>` dociąga poprawki autora. Odmawia, jeśli w worktree są
   lokalne zmiany.
3. Pokazuje tytuł PR-a (przez `gh`, jeśli jest), listę zmienionych plików
   względem `dev` i ostrzega, gdy PR zawiera migracje.
4. `node_modules` klonuje z głównego checkoutu (APFS `cp -c`, bez kosztu
   miejsca), o ile PR nie zmienia `package.json`/`yarn.lock`; inaczej
   `make assets` zrobi `yarn install`.
5. `uv sync --frozen` — każdy worktree ma własne `.venv` (wspólne `.venv`
   przez symlink psuje editable install głównego checkoutu).
6. `uv run run-site run` — losowe porty i świeże testcontainers, więc
   można to odpalić obok własnego dev-stacka, a baza po migracjach PR-a
   nie przecieka nigdzie dalej. `make assets` robi hook run-site.

**Dane do testowania.** Bez `DUMP` run-site stawia gołą bazę z baseline.
`DUMP=<host>` bierze najnowszy `db-backup-*` (`.tar.gz` z `pg_dump -Fd`,
`.pg_dump`, `.sql.gz`…) z katalogu `~/Backups/*<host>*/` — run-site sam
rozpakowuje te formaty i po odtworzeniu stosuje migracje (także te z PR-a),
więc przy okazji widać, czy przechodzą na prawdziwych danych. Żeby zawsze
startować z danymi, ustaw raz w `~/.zshrc` np. `export BPP_PR_DUMP=example`
(mały, w miarę świeży backup); `DUMP=none` wymusza wtedy gołą bazę.
Inny katalog backupów: `BPP_BACKUPS_DIR`.

Celowo **bez** `--reuse`: kontenery `--reuse` mają stałe nazwy, więc
schemat po migracjach jednego PR-a trafiłby do następnego.

Testy dotknięte przez PR odpalasz zwyczajnie w jego worktree, np.
`cd ~/Programowanie/bpp-pr-856 && uv run pytest src/integration_tests/...`.

## Changelog Management

- `towncrier create <name>.feature.rst` - Create feature changelog entry (in Polish)
- `towncrier create <name>.bugfix.rst` - Create bugfix changelog entry (in Polish)
- `towncrier create <name>.removal.rst` - Create removal changelog entry (in Polish)
- Changelog fragments are stored in `src/bpp/newsfragments/`
- Use Polish language for all changelog entries
