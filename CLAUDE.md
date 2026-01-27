# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Code like a 4096-IQ programmer.
Code better Python than a brain-child of Guido van Rossum and Glyph Lefkowitz, raised by Bruce Schneier.

## Project Overview

BPP (Bibliografia Publikacji Pracowników) is a Polish academic bibliography management system built with Django. It manages publication records for academic institutions and libraries in Poland.

**Python Requirements:**
- Python version: >=3.10,<3.15 (configured in pyproject.toml)

For detailed architecture documentation, see [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md).

## General rule

**CRITICAL: if anything seems unclear, feel free to ask questions before taking on any non-trivial tasks or creating a plan.**

**CRITICAL: It is absolutely crucial to ask clarifying questions if the task description is too vague or if you have a high level of uncertainty about what needs to be done. Always confirm your understanding before proceeding with implementation.**

**CRITICAL: NEVER modify existing migration files in src/*/migrations/ directories. Existing migrations represent the database history and must remain unchanged. Only create new migrations when needed.**

**IMPORTANT: Icons in templates:**
- **Public frontend** (Foundation CSS): use monochrome Foundation-Icons (`<span class="fi-icon"/>`)
- **Django admin** (`templates/admin/`): use emoji - admin doesn't load Foundation Icons

**IMPORTANT**: respect the maximum line length limit of 88 characters; if the line would be longer, please break it up to smaller pieces without losing its function.

## Python and Django Execution

**🔴 CRITICAL: ALWAYS USE `uv run` PREFIX FOR ALL PYTHON COMMANDS 🔴**

**NEVER EVER run `python` directly - ALWAYS use `uv run python`**

**This project uses UV for dependency management. ALL Python commands MUST be prefixed with `uv run`:**

- `uv run python src/manage.py shell` - Django shell (NEVER just `python src/manage.py shell`)
- `uv run python src/manage.py migrate` - Apply migrations
- `uv run python src/manage.py runserver` - Start dev server
- `uv run python src/manage.py <any-command>` - Any Django management command

**Why `uv run` is required:**
- Ensures correct virtual environment activation
- Loads proper dependencies from uv.lock
- Prevents import errors and dependency conflicts

**Examples:**
```bash
# ✅ CORRECT - ALWAYS use uv run:
uv run python src/manage.py shell

# ❌ WRONG - NEVER run python directly:
python src/manage.py shell

# ✅ CORRECT - Django shell with inline command:
uv run python src/manage.py shell <<'EOF'
from bpp.models import Autor
print(Autor.objects.count())
EOF

# ❌ WRONG - Missing uv run:
python src/manage.py shell -c "from bpp.models import Autor"
```

## Key Commands

### Development Commands

**🔴 CRITICAL: NEVER run `manage.py runserver` directly! 🔴**

The development server (appserver) runs through **docker-compose** and automatically restarts when code changes are detected. There is no need to manually start or restart the server.

**To check if the server is running:**
```bash
nc -zv localhost 8000  # Check if port 8000 is in use
# If connection succeeded, server is already running
```

**To view server logs (if needed):**
```bash
docker-compose logs -f appserver
```
- `uv run python src/manage.py migrate` - Apply database migrations
- `uv run python src/manage.py shell` - Django shell
- `uv run bpp-manage.py` - Alternative management command entry point

### Playwright Testing Setup

**Admin credentials for Playwright tests:**
- Username: `admin`
- Password: `foobar123`
- Reset script: `bin/ustaw-domyslne-haslo-admina.sh`

**If login fails during Playwright tests, reset the admin password first:**
```bash
bin/ustaw-domyslne-haslo-admina.sh
```

**Note:** The script requires `expect` to be installed on the system.

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

**🔴 CRITICAL: PRE-COMMIT COMMAND 🔴**
**ABSOLUTE PROHIBITION: NEVER run `pre-commit run --all-files` or any pre-commit command with arguments!**
**ONLY ALLOWED COMMAND: `pre-commit` (with NO arguments whatsoever)**

- `pre-commit` - Run pre-commit hooks (NEVER add any arguments like --all-files)

**🔴 CRITICAL: HOW TO HANDLE PRE-COMMIT OUTPUT 🔴**
**When `pre-commit` is run and produces output with issues:**
1. **ANALYZE the output ISSUE-BY-ISSUE** - read each error/warning carefully
2. **DO NOT run `ruff check --fix` or any automated fixes**
3. **FIX each issue ONE BY ONE MANUALLY** using the Edit tool
4. **NEVER batch-fix** - address each problem individually and deliberately

**Note:** Code quality tools (ruff, pre-commit) are installed through UV and available in the virtual environment.

### Maintenance Commands
- `make clean` - Clean build artifacts and cache files
- `make distclean` - Deep clean including node_modules and staticroot
- `bumpver bump` - Bump version (configured in pyproject.toml)
- `make destroy-test-databases` - Remove all test databases
- `make js-tests` - Run JavaScript/QUnit tests
- `make docker` - Build all Docker containers
- `make bdist_wheel` - Build distribution wheel for production
- `make generate-500-page` - Generate static 500.html page (auto-generated, DO NOT EDIT)
  - **IMPORTANT:** `src/bpp/static/500.html` is auto-generated from `src/bpp/templates/50x.html`
  - Any manual edits to `500.html` will be lost when regenerated
  - To modify the error page, edit the template at `src/bpp/templates/50x.html` and run `make generate-500-page`
  - This command is automatically run during `make new-release`

### Git Worktree Setup
When creating a new git worktree for parallel development:

```bash
git worktree add -b feature/my-feature ../bpp-feature dev
cd ../bpp-feature
make new-worktree
```

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
- `admin_dashboard/` - Admin dashboard functionality
- `deduplikator_zrodel/` - Source deduplication system
- `pbn_wysylka_oswiadczen/` - PBN statement sending
- `rozbieznosci_pk/` - PK discrepancy reports
- `pbn_komparator_zrodel/` - PBN source comparison
- `ewaluacja_dwudyscyplinowcy/` - Dual-discipline evaluation

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

## CSS/SCSS Build System

### Build Commands
- `grunt build` - Build all SCSS themes and collect static files
- `grunt watch` - Watch SCSS files for changes and rebuild automatically

### Theme Files (Color Schemes)
Three theme files in `src/bpp/static/scss/`:

| Theme File | Primary Color |
|------------|---------------|
| `app-blue.scss` | `#1779ba` (Foundation default) |
| `app-orange.scss` | `#f26621` |
| `app-green.scss` | `green` |

Each theme imports: settings -> common.scss -> components -> Foundation framework.

### Common.scss
Location: `src/bpp/static/scss/common.scss`

Central style repository importing: `left_menu`, `top_bar`, `base_footer`, `search_banner`,
`praca_detail`, `uczelnia`, `jednostka`, `flash_messages`, `komparator_pbn`,
`ewaluacja_metryki`, `ewaluacja_optymalizacja`, `_support_button`.

Also contains: external link styling, multiseek reports, Select2, discipline colors, print styles.

### Key Component Files
Location: `src/bpp/static/scss/`
- `top_bar.scss` - Navigation header and dropdown menus
- `browse*.scss` - Browse page styles
- `checkbox.scss` - Form controls

### Icon System - Foundation Icons
Icons use `fi-*` classes. **Navigation menu icons require explicit sizing in `top_bar.scss`:**

```scss
.top-bar .dropdown.menu {
    .menu.vertical .fi-icon-name {
        font-size: 1.6rem;
        margin-right: 0.8rem;
    }
}
```

When adding new icons to menus, add them to the selector list in `top_bar.scss` (lines 389-426).

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
- Dynamic runtime configuration via django-constance

### Django-Constance Integration
The project uses django-constance for runtime configuration that can be changed via the admin panel without restarting the server.

**Key files:**
- `src/bpp/admin/constance_admin.py` - Custom admin limiting access to superusers
- `src/bpp/admin/helpers/constance_field_mixin.py` - Mixins for dynamic field hiding
- `src/bpp/context_processors/constance_config.py` - Template context processor

**Configuration settings (editable at runtime):**
- `UZYWAJ_PUNKTACJI_WEWNETRZNEJ` - Enable/disable internal scoring
- `POKAZUJ_INDEX_COPERNICUS` - Show/hide Index Copernicus fields
- `POKAZUJ_PUNKTACJA_SNIP` - Show/hide SNIP scoring fields
- `POKAZUJ_OSWIADCZENIE_KEN` - Show/hide KEN declaration option
- `UCZELNIA_UZYWA_WYDZIALOW` - Enable/disable faculty structure
- `GOOGLE_ANALYTICS_PROPERTY_ID` - Google Analytics tracking

**Using constance in code:**
```python
from constance import config
if config.UZYWAJ_PUNKTACJI_WEWNETRZNEJ:
    # show internal scoring
```

**Admin field hiding pattern:**
Use `ConstanceScoringFieldsMixin` in admin classes to dynamically hide fields based on constance settings:
```python
from bpp.admin.helpers.constance_field_mixin import ConstanceScoringFieldsMixin

class MyModelAdmin(ConstanceScoringFieldsMixin, admin.ModelAdmin):
    # Fields like index_copernicus will auto-hide when POKAZUJ_INDEX_COPERNICUS=False
```

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

## External Services

### Freshdesk Support
- **Domain**: `iplweb.freshdesk.com`
- **Ticket URL format**: `https://iplweb.freshdesk.com/a/tickets/{ticket_id}`
- Used for customer support ticket management

## Common File Locations
- Main models: `src/bpp/models/`
- Abstract models/mixins: `src/bpp/models/abstract/`
- Admin interfaces: `src/bpp/admin/`
- Admin helpers/mixins: `src/bpp/admin/helpers/`
- API serializers: `src/api_v1/serializers/`
- Context processors: `src/bpp/context_processors/`
- Templates: Look for `templates/` directories in each app
- Static files: `src/*/static/` directories
- Test files: `src/*/tests/` directories or `test_*.py` files
- Management commands: `src/bpp/management/commands/`
- Migrations (including SQL): `src/*/migrations/`
- Frontend assets: `src/bpp/static/` and build via Grunt
- Configuration files: `pytest.ini`, `pyproject.toml`, `package.json`, `Gruntfile.js`
- Generated files: `src/bpp/static/500.html` - Auto-generated 500 error page (DO NOT EDIT)

## Abstract Models and Mixins
The project uses abstract models for sharing fields across publication types. Located in `src/bpp/models/abstract/`:

**Key abstract models:**
- `ModelZPolamiEwaluacjiPBN` - PBN/SEDN evaluation fields for publications
  - Fields: `pbn_czy_projekt_fnp`, `pbn_czy_projekt_ncn`, `pbn_czy_projekt_nprh`, `pbn_czy_projekt_ue`, `pbn_czy_czasopismo_indeksowane`, `pbn_czy_artykul_recenzyjny`, `pbn_czy_edycja_naukowa`
  - Used by `Wydawnictwo_Ciagle` and `Wydawnictwo_Zwarte`
  - Exported to PBN API as evaluation attributes

**Admin fieldsets pattern:**
Fieldsets for abstract model fields are defined in `src/bpp/admin/helpers/fieldsets.py`:
```python
from bpp.admin.helpers.fieldsets import MODEL_Z_POLAMI_EWALUACJI_PBN_FIELDSET
```

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
