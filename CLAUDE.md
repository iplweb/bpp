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

### Code Quality Commands
- `black .` - Format Python code
- `isort .` - Sort Python imports
- `flake8` - Lint Python code
- `pre-commit run --all-files` - Run pre-commit hooks

### Maintenance Commands
- `make clean` - Clean build artifacts and cache files
- `make distclean` - Deep clean including node_modules and staticroot
- `bumpver bump` - Bump version (configured in pyproject.toml)

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
- `django_bpp/settings/base.py` - Base settings
- `django_bpp/settings/local.py` - Development settings
- `django_bpp/settings/production.py` - Production settings
- `django_bpp/settings/test.py` - Test settings

### Key Features
- Multi-institutional academic publication management
- Author and institution tracking
- Publication scoring and ranking systems
- Integration with external academic databases (PBN, CrossRef, Clarivate)
- Advanced reporting and analytics
- ORCID integration for author identification
- Open Access classification and tracking

### Development Notes
- Uses Poetry for Python dependency management
- Extensive test suite with pytest and Selenium integration
- Pre-commit hooks for code quality
- Celery for background task processing
- Django Channels for WebSocket support
- Internationalization support (Polish primary language)

## Common File Locations
- Main models: `src/bpp/models/`
- Admin interfaces: `src/bpp/admin/`
- API serializers: `src/api_v1/serializers/`
- Templates: Look for `templates/` directories in each app
- Static files: `src/*/static/` directories
- Test files: `src/*/tests/` directories or `test_*.py` files
