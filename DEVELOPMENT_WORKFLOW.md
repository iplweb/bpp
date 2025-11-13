# BPP Development Workflow

This document describes the development workflow for the BPP (Bibliografia Publikacji Pracowników) project.

## Version Management

### Version Pattern

This project uses **CalVer** (Calendar Versioning) with the pattern: `YYYYMM.BUILD[-TAG[TAGNUM]]`

**Example versions:**
- `202510.1274` - Release version
- `202510.1275-dev1` - First development version
- `202510.1275-dev2` - Second development version (after additional changes)
- `202510.1275` - Final release (dev tag removed)

### Development Cycle Workflow

#### 1. Start Development on Next Version

After releasing `v202510.1274`, start development on the next version:

```bash
make bump-dev
```

This creates `v202510.1275-dev1` and automatically updates:
- `pyproject.toml` (version fields)
- `src/django_bpp/version.py` (VERSION constant)
- `package.json` (version field)
- `Makefile` (DOCKER_VERSION variable)

#### 2. During Development

Build and tag Docker images with the development version:

```bash
# Build all services with version tags
docker compose build

# This creates images tagged as both:
# - iplweb/bpp_appserver:202510.1275.dev1
# - iplweb/bpp_appserver:latest
```

Start development services:

```bash
docker compose up -d
```

#### 3. Ready for Release

Remove the `-dev` tag to create the final release version:

```bash
make bump-release
```

This creates `v202510.1275` (final release version).

#### 4. Release and Start Next Dev Cycle (Combined)

Or combine steps 3 and 1 in a single command:

```bash
make bump-and-start-dev
```

This:
1. Releases the current version (removes `-dev` tag): `v202510.1275`
2. Immediately starts the next dev cycle: `v202510.1276-dev1`

## Docker Development Setup

### Environment Configuration

The project uses `docker-compose.yml` configured for development with:

- **Live source code mounting**: `./src:/app/src` mounted on all services
- **Development settings**: `DJANGO_SETTINGS_MODULE=django_bpp.settings.local`
- **Exposed ports**: All service ports are accessible for debugging
- **Version tagging**: Automatic version tagging using `${DOCKER_VERSION:-latest}`

### Building Docker Images

```bash
# Build all services
docker compose build

# Build specific service
docker compose build appserver

# Build without cache (clean rebuild)
docker compose build --no-cache

# Build with specific version
export DOCKER_VERSION="202510.1275.dev1"
docker compose build
```

### Running Services

```bash
# Start all services
docker compose up -d

# Start specific service
docker compose up -d appserver

# View logs
docker compose logs -f appserver

# Restart after code changes that require restart
docker compose restart appserver
```

### Pushing Images to Registry

```bash
# Push all services (with both version and latest tags)
docker compose push

# Push specific service
docker compose push appserver
```

## Testing Workflow

### Running Tests Locally

**CRITICAL: Always use `uv run pytest` - NEVER run pytest directly**

```bash
# Run all tests (takes up to 10 minutes)
uv run pytest

# Run tests for specific app
uv run pytest src/bpp/

# Run specific test file
uv run pytest src/bpp/tests/test_views/test_auth.py

# Run specific test function
uv run pytest src/bpp/tests/test_views/test_auth.py::test_login

# Run with verbose output
uv run pytest -v

# Run tests excluding Selenium (faster)
make tests-without-selenium

# Run only Selenium tests
make tests-with-selenium
```

### Test Configuration

- Tests use `--reuse-db` option by default for faster execution
- Default Django settings: `django_bpp.settings.local` (configured in `pytest.ini`)
- Fixtures available in `src/conftest.py` and subdirectories
- Test database is automatically created and reused

## Code Quality

### Formatting and Linting

```bash
# Format Python code
ruff format .

# Check linting issues
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Run all pre-commit hooks
pre-commit run --all-files
```

### Before Committing

The project has pre-commit hooks installed that automatically run on `git commit`. These check:
- Code formatting (ruff)
- Import sorting
- Trailing whitespace
- YAML/JSON syntax
- And more...

## Frontend Development

### Building Frontend Assets

**IMPORTANT**: After changing any SCSS files, run:

```bash
grunt build
```

Or use the combined command:

```bash
make assets
```

This runs:
1. `yarn install` - Install Node.js dependencies
2. `grunt build` - Build frontend assets
3. `python src/manage.py collectstatic` - Collect static files

### Frontend File Structure

- SCSS files: `src/bpp/static/`
- Compiled CSS: Built by Grunt
- JavaScript: jQuery, HTMX, DataTables, Select2

**CRITICAL**: Never override Foundation's grid classes (like `medium-4`, `large-12`) in SCSS. Change column widths in HTML templates instead.

## Django Development Server

### Starting the Local Development Server

**CRITICAL: Always check if the server is already running:**

```bash
# Check if port 8000 is in use
nc -zv localhost 8000

# If not running, start the server
python src/manage.py runserver
```

**Note**: If you see "Address already in use" error, the server is already running in the background - no action needed.

### Common Django Commands

```bash
# Apply database migrations
python src/manage.py migrate

# Create new migrations
python src/manage.py makemigrations

# Django shell (for model queries)
python src/manage.py shell

# Create superuser
python src/manage.py createsuperuser

# Collect static files
python src/manage.py collectstatic
```

## Celery Development

### Celery Commands

```bash
# Inspect registered tasks
uv run celery -A django_bpp.celery_tasks inspect registered

# Purge all tasks from queues
uv run celery -A django_bpp.celery_tasks purge -Q denorm,celery -f

# Monitor Celery workers
uv run celery -A django_bpp.celery_tasks inspect active
```

## Database Migrations

**CRITICAL: NEVER modify existing migration files in `src/*/migrations/` directories.**

Existing migrations represent the database history and must remain unchanged. Only create new migrations when needed.

### Creating Migrations

```bash
# Create migrations for all apps
python src/manage.py makemigrations

# Create migration for specific app
python src/manage.py makemigrations bpp

# Show SQL for migration
python src/manage.py sqlmigrate bpp 0001
```

## Changelog Management

The project uses `towncrier` for changelog management. All changelog entries should be in **Polish**.

### Creating Changelog Entries

```bash
# Feature changelog
towncrier create <name>.feature.rst

# Bugfix changelog
towncrier create <name>.bugfix.rst

# Removal changelog
towncrier create <name>.removal.rst
```

Changelog fragments are stored in `src/bpp/newsfragments/`.

## Git Workflow

The project uses git-flow workflow:

- `dev` - Main development branch
- `feature/*` - Feature branches
- `release/*` - Release branches
- `hotfix/*` - Hotfix branches

### Creating a Release

The full release process (handled by `make new-release`):

1. Lock dependencies: `uv lock`
2. Create release branch
3. Bump version
4. Build changelog with towncrier
5. Merge to main and dev
6. Push and trigger Docker image builds
7. Watch GitHub Actions for Docker builds

## Environment Variables

### Required for Docker Development

Create `.env.docker` file with:

```bash
DJANGO_BPP_DB_HOST=db
DJANGO_BPP_DB_NAME=bpp
DJANGO_BPP_DB_USER=bpp_user
DJANGO_BPP_DB_PASSWORD=your_password
DJANGO_BPP_RABBITMQ_USER=bpp
DJANGO_BPP_RABBITMQ_PASS=bpp
```

### Optional: Override Docker Version

```bash
export DOCKER_VERSION="202510.1275.dev1"
docker compose build
```

## Troubleshooting

### Port Already in Use

If you see "Address already in use" errors, check which services are running:

```bash
# Check if port 8000 is in use (Django)
nc -zv localhost 8000

# Check if port 5432 is in use (PostgreSQL)
nc -zv localhost 5432

# Check if port 6379 is in use (Redis)
nc -zv localhost 6379
```

### Docker Services Not Starting

```bash
# View logs for specific service
docker compose logs -f appserver

# Restart all services
docker compose restart

# Rebuild and restart
docker compose up -d --build
```

### Database Issues

```bash
# Reset database (DESTRUCTIVE)
docker compose down -v
docker compose up -d db
python src/manage.py migrate
```

### Test Database Issues

```bash
# Remove all test databases
make destroy-test-databases
```

## Summary of Key Commands

| Task | Command |
|------|---------|
| Start dev version | `make bump-dev` |
| Create release | `make bump-release` |
| Release + start next dev | `make bump-and-start-dev` |
| Build Docker images | `docker compose build` |
| Start services | `docker compose up -d` |
| Run tests | `uv run pytest` |
| Format code | `ruff format .` |
| Build frontend | `grunt build` |
| Start Django server | `python src/manage.py runserver` |
| Django shell | `python src/manage.py shell` |
| Apply migrations | `python src/manage.py migrate` |
