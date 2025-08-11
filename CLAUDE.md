# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BPP (Bibliografia Publikacji Pracowników) is a Polish academic bibliography management system built with Django. It manages publication records for academic institutions and libraries in Poland.

## Key Commands

### Development Commands
- `python src/manage.py runserver` - Start development server (default settings: django_bpp.settings.local)
- `python src/manage.py migrate` - Apply database migrations
- `python src/manage.py collectstatic` - Collect static files
- `python src/manage.py shell` - Django shell
- `bpp-manage.py` - Alternative management command entry point

### Frontend Build Commands
- `yarn install` - Install Node.js dependencies
- `grunt build` - Build frontend assets using Grunt
- `make assets` - Run both yarn install and grunt build
- `make collectstatic` - Collect Django static files

### Testing Commands
- `pytest` - Run tests (configured in pytest.ini)
- `pytest --ds=django_bpp.settings.local` - Run tests with specific settings
- `pytest --selenium` - Include Selenium tests (marked with @pytest.mark.selenium)
- `pytest -k "not selenium"` - Run tests excluding Selenium tests
- `make tests-without-selenium` - Run tests excluding Selenium tests with parallelization
- `make tests-with-selenium` - Run only Selenium tests with parallelization
- `make tests` - Run complete test suite including JS tests
- `make full-tests` - Run tests with Microsoft Auth integration

### Code Quality Commands
- `black .` - Format Python code
- `isort .` - Sort Python imports
- `flake8` - Lint Python code
- `pre-commit run --all-files` - Run pre-commit hooks

### Maintenance Commands
- `make clean` - Clean build artifacts and cache files
- `make distclean` - Deep clean including node_modules and staticroot
- `bumpver bump` - Bump version (configured in pyproject.toml)
- `make destroy-test-databases` - Remove all test databases
- `make js-tests` - Run JavaScript/QUnit tests
- `make docker` - Build all Docker containers
- `make bdist_wheel` - Build distribution wheel for production

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

**Reporting Applications:**
- `raport_slotow/` - Slot reporting system
- `ranking_autorow/` - Author ranking system
- `ewaluacja2021/` - 2021 evaluation reports
- `nowe_raporty/` - New reporting system

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

### Database
- PostgreSQL database with custom SQL functions and triggers
- Complex migration system with SQL files for database views and functions
- Location: `src/bpp/migrations/` contains both Python and SQL migrations

### Frontend
- Foundation CSS framework
- jQuery and various plugins (DataTables, Select2, HTMX)
- Grunt build system for asset compilation
- Static files management via Django's collectstatic

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
- Uses Poetry for Python dependency management (pyproject.toml)
- Extensive test suite with pytest and Selenium integration
- Pre-commit hooks for code quality
- Celery for background task processing
- Django Channels for WebSocket support
- Internationalization support (Polish primary language)
- Docker support with multi-architecture builds
- Yarn for Node.js dependency management
- Grunt for frontend asset compilation

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
