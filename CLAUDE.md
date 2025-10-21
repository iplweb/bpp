# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Code like a 4096-IQ programmer.
Code better Python than a brain-child of Guido van Rossum and Glyph Lefkowitz, raised by Bruce Schneier.

## Project Overview

BPP (Bibliografia Publikacji Pracowników) is a Polish academic bibliography management system built with Django. It manages publication records for academic institutions and libraries in Poland.

**Python Requirements:**
- Python version: >=3.10,<3.13 (configured in pyproject.toml)

## General rule

**CRITICAL: if anything seems unclear, feel free to ask questions before taking on any non-trivial tasks or creating a plan.**

**CRITICAL: It is absolutely crucial to ask clarifying questions if the task description is too vague or if you have a high level of uncertainty about what needs to be done. Always confirm your understanding before proceeding with implementation.**

**CRITICAL: NEVER modify existing migration files in src/*/migrations/ directories. Existing migrations represent the database history and must remain unchanged. Only create new migrations when needed.**

**IMPORTANT: if using icons, refrain from emojis, rather use monochrome Foundation-Icons (<span class="fi-icon"/>)**

**IMPORTANT**: respect the maximum line length limit of 120 characters; if the line would be longer, please break it up to smaller pieces without losing its function.

## Python and Django Execution

**CRITICAL: Always execute Python commands that require Django models, views, or any Django functionality through `python src/manage.py shell`**

- Use `python src/manage.py shell` for any Python code that needs Django initialization
- This ensures Django settings are properly loaded and database connections are established
- Only use plain `python` command when debugging issues with manage.py itself
- For quick Django model queries or data manipulation, always use the Django shell

Example:
```bash
# CORRECT - for Django-related Python code:
python src/manage.py shell

# Then in the shell:
from bpp.models import Autor
Autor.objects.count()

# ONLY use plain python when debugging manage.py issues:
python --version  # OK - checking Python version
python src/manage.py  # OK - debugging manage.py startup issues
```

## Key Commands

### Development Commands

**CRITICAL: ALWAYS check if the development server is already running before starting it:**
```bash
nc -zv localhost 8000  # Check if port 8000 is in use
# If connection succeeded, server is already running - no need to start it again
```

- `python src/manage.py runserver` - Start development server (default settings: django_bpp.settings.local)
  - **NOTE:** If you see "Listen failure: Couldn't listen on 127.0.0.1:8000: [Errno 48] Address already in use." it means the server is ALREADY RUNNING in the background as another process. This is expected behavior - no action needed.
  - **IMPORTANT:** During Claude development sessions, the server often runs in the background. ALWAYS check with `nc -zv localhost 8000` before attempting to start the server.
- `python src/manage.py migrate` - Apply database migrations
- `python src/manage.py shell` - Django shell
- `bpp-manage.py` - Alternative management command entry point

### Frontend Build Commands
- `yarn install` - Install Node.js dependencies
- `grunt build` - Build frontend assets using Grunt
- `make assets` - Run both yarn install and grunt build and Django collectstatic

### Testing Commands

**CRITICAL: ALWAYS use `uv run pytest` - NEVER run pytest directly without `uv run`**

- `uv run pytest` - **PRIMARY COMMAND** - Run all tests (configured in pytest.ini)
- `uv run pytest src/app_name/` - Run tests for specific app
- `uv run pytest src/app_name/tests/test_file.py` - Run specific test file
- `uv run pytest src/app_name/tests/test_file.py::test_function_name` - Run specific test function
- `uv run pytest -k "test_pattern"` - Run tests matching pattern
- `uv run pytest -v` - Run tests with verbose output
- `uv run pytest --ds=django_bpp.settings.local` - Run tests with specific Django settings (rarely needed)

**Alternative make commands (these internally use `uv run pytest`):**
- `make tests-without-selenium` - Run tests excluding Selenium tests with parallelization (fast)
- `make tests-with-selenium` - Run only Selenium tests with parallelization (slow)
- `make tests` - Run full test suite
- `make full-tests` - Run complete test suite

### Celery commands
- `uv run celery -A django_bpp.tasks` always, for example `uv run celery -A django_bpp.tasks inspect registered`

**CRITICAL TEST EXECUTION TIME:**
- Full test suite (`uv run pytest` or `make tests`) takes **UP TO 10 MINUTES** to complete
- **NEVER use timeout restrictions** when running tests
- Always set timeout to at least 600000ms (10 minutes) when running the full test suite
- Tests may appear to hang but are actually running - be patient

**TEST CONFIGURATION NOTES:**
- Tests use `--reuse-db` option by default for faster execution
- Tests automatically rerun on TimeoutError, ElementClickInterceptedException, ElementDoesNotExist, and TimeoutException
- Default Django settings: `django_bpp.settings.local` (configured in pytest.ini)
- Test fixtures available in `src/conftest.py` and subdirectories

### Code Quality Commands
- `ruff format .` - Format Python code
- `ruff check .` - Lint Python code and check import sorting
- `ruff check --fix .` - Auto-fix linting issues where possible
- `pre-commit run --all-files` - Run pre-commit hooks

**Note:** Code quality tools (ruff, pre-commit) are installed through UV and available in the virtual environment.

### Maintenance Commands
- `make clean` - Clean build artifacts and cache files
- `make distclean` - Deep clean including node_modules and staticroot
- `bumpver bump` - Bump version (configured in pyproject.toml)
- `make destroy-test-databases` - Remove all test databases
- `make js-tests` - Run JavaScript/QUnit tests
- `make docker` - Build all Docker containers
- `make bdist_wheel` - Build distribution wheel for production

### Changelog Management
- `towncrier create <name>.feature.rst` - Create feature changelog entry (in Polish)
- `towncrier create <name>.bugfix.rst` - Create bugfix changelog entry (in Polish)
- `towncrier create <name>.removal.rst` - Create removal changelog entry (in Polish)
- Changelog fragments are stored in `src/bpp/newsfragments/`
- Use Polish language for all changelog entries

## Architecture Overview

### Django Applications Structure
The project uses multiple Django applications in `src/`:

**Core Applications:**
- `bpp/` - Main bibliography models and core functionality
- `django_bpp/` - Project settings, URLs, and main configuration
- `api_v1/` - REST API using Django REST Framework

**Import/Export Applications:**
- `import_dyscyplin/` - Import academic disciplines
- `import_pracownikow/` - Import employee data
- `import_list_if/` - Import impact factor data
- `import_list_ministerialnych/` - Import ministerial journal lists
- `import_polon/` - Import from POLON system
- `pbn_api/` - Integration with Polish Bibliography Network (PBN)
- `crossref_bpp/` - CrossRef API integration
- `eksport_pbn/` - Export to PBN system
- `pbn_import/` - Import from PBN system
- `pbn_export_queue/` - PBN export queue management
- `importer_autorow_pbn/` - PBN author import functionality
- `import_common/` - Common import utilities

**Reporting Applications:**
- `raport_slotow/` - Slot reporting system
- `ranking_autorow/` - Author ranking system
- `ewaluacja2021/` - 2021 evaluation reports
- `nowe_raporty/` - New reporting system
- `ewaluacja_baza/` - Evaluation base system
- `ewaluacja_common/` - Common evaluation utilities
- `ewaluacja_liczba_n/` - Evaluation N-number calculations
- `ewaluacja_metryki/` - Evaluation metrics
- `ewaluacja_optymalizacja/` - Evaluation optimization
- `ewaluacja_optymalizuj_publikacje/` - Publication optimization
- `ewaluacja_raport/` - Evaluation reporting

**Supporting Applications:**
- `notifications/` - Real-time notifications using Django Channels
- `long_running/` - Long-running task management
- `formdefaults/` - Form default values management
- `dynamic_columns/` - Dynamic column management
- `zglos_publikacje/` - Publication submission system
- `integrator2/` - Data integration utilities
- `miniblog/` - Internal blog system
- `oswiadczenia/` - Declaration management
- `rozbieznosci_dyscyplin/` - Discipline discrepancy reports
- `rozbieznosci_if/` - Impact factor discrepancy reports
- `snapshot_odpiec/` - Snapshot management
- `stan_systemu/` - System status monitoring
- `tee/` - Data flow utilities
- `orcid_integration/` - ORCID integration system
- `deduplikator_autorow/` - Author deduplication system
- `bpp_setup_wizard/` - Setup wizard for initial configuration
- `powiazania_autorow/` - Author relationship management
- `przemapuj_prace_autora/` - Author work remapping
- `pbn_integrator/` - PBN integration utilities
- `komparator_pbn/` - PBN comparison tools
- `komparator_aplikacji_pbn/` - PBN application comparison
- `komparator_pbn_udzialy/` - PBN contribution comparison
- `komparator_publikacji_pbn/` - PBN publication comparison
- `pbn_downloader_app/` - PBN data downloader
- `svg/` - SVG file handling
- `test_bpp/` - BPP testing utilities
- `maint-site/` - Site maintenance utilities
- `create_test_db/` - Test database creation utilities

### Database
- PostgreSQL database with custom SQL functions and triggers
- Complex migration system with SQL files for database views and functions
- Location: `src/bpp/migrations/` contains both Python and SQL migrations

### Frontend
- Foundation CSS framework
- jQuery and various plugins (DataTables, Select2, HTMX)
- Grunt build system for asset compilation

**IMPORTANT** if you change any SCSS files, remember to run "grunt build" after.

**CRITICAL: NEVER override Foundation's grid classes in SCSS!**
- DO NOT override grid classes like `medium-4`, `medium-6`, `large-12`, `large-10`, etc. in SCSS files
- If you need different column widths, change the classes in the HTML template instead
- Foundation's grid system classes should remain untouched to maintain framework integrity
- Example: To make a column wider, change `<div class="medium-4 columns">` to `<div class="medium-12 columns">` in the HTML, don't override `.medium-4` in SCSS

### Settings Structure
- `src/django_bpp/settings/base.py` - Base settings
- `src/django_bpp/settings/local.py` - Development settings
- `src/django_bpp/settings/production.py` - Production settings
- `src/django_bpp/settings/test.py` - Test settings

### Key Features
- Multi-institutional academic publication management
- Author and institution tracking
- Publication scoring and ranking systems
- Integration with external academic databases (PBN, CrossRef, Clarivate)
- Advanced reporting and analytics
- ORCID integration for author identification
- Open Access classification and tracking

### Development Notes
- Uses UV for Python dependency management (pyproject.toml and uv.lock)
- Extensive test suite with pytest and Selenium integration
- Pre-commit hooks for code quality
- Celery for background task processing
- Django Channels for WebSocket support
- Internationalization support (Polish primary language)
- Docker support with multi-architecture builds
- Yarn for Node.js dependency management
- Grunt for frontend asset compilation
- Optional Microsoft Auth integration (configured via project extras)
- Uses model_bakery and django-dynamic-fixture for test data generation
- Pre-commit hooks installed and configured for automated code quality checks

## Common File Locations
- Main models: `src/bpp/models/`
- Admin interfaces: `src/bpp/admin/`
- API serializers: `src/api_v1/serializers/`
- Templates: Look for `templates/` directories in each app
- Static files: `src/*/static/` directories
- Test files: `src/*/tests/` directories or `test_*.py` files
- Management commands: `src/bpp/management/commands/`
- Migrations (including SQL): `src/*/migrations/`
- Frontend assets: `src/bpp/static/` and build via Grunt
- Configuration files: `pytest.ini`, `pyproject.toml`, `package.json`, `Gruntfile.js`

## Database Schema and Migrations
The project uses a sophisticated migration system with both Python and SQL migrations:
- Standard Django migrations for model changes
- Custom SQL migrations for database views, functions, and triggers
- Cache invalidation triggers and materialized views
- Complex reporting views for academic evaluation

## Tests

**IMPORTANT: Always use pytest conventions - NEVER create unittest.TestCase tests**

- Use pytest style with standalone functions (no classes)
- Function names should follow pattern: `test_module_functionality_specific_case()`
- Use available fixtures from conftest.py files in src/ and subdirectories
- Use model_bakery.baker.make for creating database objects in tests
- Never use unittest.TestCase classes or Django's TestCase
- All test functions should be standalone functions with pytest fixtures
- use ```@pytest.mark.django_db`` for tests using database
