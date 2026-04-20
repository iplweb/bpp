# Claude Code Web Environment Setup

When running in Claude Code web environment (cloud sandbox),
the following setup steps are needed before running tests.
These steps handle missing system packages, services, and
workarounds for network restrictions in the sandbox.

## 1. Configure apt to use HTTPS (network proxy workaround)

The sandbox routes traffic through an egress proxy that only
allows HTTPS to whitelisted domains. Apt must use HTTPS:

```bash
# Switch apt sources to HTTPS
sudo sed -i \
  's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' \
  /etc/apt/sources.list.d/ubuntu.sources
sudo sed -i \
  's|http://security.ubuntu.com|https://security.ubuntu.com|g' \
  /etc/apt/sources.list.d/ubuntu.sources
sudo apt-get update
```

## 2. Install system dependencies

```bash
sudo apt-get install -y \
  libpq-dev libcairo2-dev libpango1.0-dev \
  libgdk-pixbuf2.0-dev libffi-dev \
  libgirepository1.0-dev libgtk-3-dev \
  libldap2-dev libsasl2-dev python3-dev \
  postgresql-plpython3-16
```

## 3. Generate Polish locale and restart PostgreSQL

```bash
sudo locale-gen pl_PL.UTF-8
sudo pg_ctlcluster 16 main restart
```

## 4. Configure PostgreSQL for local trust auth

```bash
sudo sed -i \
  's/^local.*all.*all.*peer/local   all   all   trust/' \
  /etc/postgresql/16/main/pg_hba.conf
sudo sed -i \
  's/^host.*all.*all.*127.0.0.1\/32.*scram-sha-256/host    all   all   127.0.0.1\/32   trust/' \
  /etc/postgresql/16/main/pg_hba.conf
sudo pg_ctlcluster 16 main reload
```

## 5. Create database user and database

```bash
sudo -u postgres psql -c \
  "CREATE USER bpp WITH PASSWORD '' SUPERUSER;"
sudo -u postgres psql -c \
  "CREATE DATABASE bpp OWNER bpp;"
```

## 6. Start Redis

```bash
redis-server --daemonize yes
```

## 7. Create .env file

```bash
cat > .env << 'EOF'
DJANGO_SETTINGS_MODULE="django_bpp.settings.local"
DEBUG=true
DJANGO_BPP_HOSTNAME="localhost"
DJANGO_BPP_SECRET_KEY="test-secret-key-for-local-dev"
DJANGO_BPP_DB_NAME="bpp"
DJANGO_BPP_DB_USER="bpp"
DJANGO_BPP_DB_PASSWORD=""
DJANGO_BPP_DB_HOST="localhost"
DJANGO_BPP_DB_PORT="5432"
DJANGO_BPP_DB_DISABLE_SSL=1
DJANGO_BPP_REDIS_HOST="localhost"
DJANGO_BPP_REDIS_PORT="6379"
DJANGO_BPP_REDIS_DB_CELERY="2"
DJANGO_BPP_REDIS_DB_SESSION="4"
DJANGO_BPP_REDIS_DB_CACHE="5"
DJANGO_BPP_REDIS_DB_LOCKS="6"
DJANGO_BPP_RABBITMQ_HOST="localhost"
DJANGO_BPP_RABBITMQ_PORT="5672"
DJANGO_BPP_RABBITMQ_USER="bpp"
DJANGO_BPP_RABBITMQ_PASS="bpp"
DJANGO_BPP_UZYWAJ_PUNKTACJI_WEWNETRZNEJ="0"
DJANGO_BPP_PUNKTUJ_MONOGRAFIE="0"
DJANGO_BPP_INLINE_DLA_AUTOROW="stacked"
DJANGO_BPP_THEME_NAME="app-blue"
DJANGO_BPP_SESSION_SECURITY_WARN_AFTER="25200"
DJANGO_BPP_SESSION_SECURITY_EXPIRE_AFTER="28800"
DJANGO_BPP_PASSWORD_DURATION_SECONDS="315360000"
DJANGO_BPP_USE_PASSWORD_HISTORY="1"
DJANGO_BPP_PASSWORD_HISTORY_COUNT="1"
EOF
```

## 8. Install Python dependencies

```bash
uv sync --all-extras
```

**psycopg2 workaround:** Even with `libpq-dev` installed,
`uv sync` may still try to build `psycopg2` from source and
fail. If so, install `psycopg2-binary` and create a fake
dist-info so uv considers the dependency satisfied:

```bash
uv pip install psycopg2-binary==2.9.11

SITE_PKG=$(.venv/bin/python -c \
  "import site; print(site.getsitepackages()[0])")
mkdir -p "$SITE_PKG/psycopg2-2.9.11.dist-info"

cat > "$SITE_PKG/psycopg2-2.9.11.dist-info/METADATA" << 'EOF'
Metadata-Version: 2.1
Name: psycopg2
Version: 2.9.11
EOF

cat > "$SITE_PKG/psycopg2-2.9.11.dist-info/RECORD" << 'EOF'
psycopg2/__init__.py,sha256=,
psycopg2-2.9.11.dist-info/METADATA,sha256=,
psycopg2-2.9.11.dist-info/RECORD,,
EOF

echo "uv" > \
  "$SITE_PKG/psycopg2-2.9.11.dist-info/INSTALLER"

cat > "$SITE_PKG/psycopg2-2.9.11.dist-info/WHEEL" << 'EOF'
Wheel-Version: 1.0
Generator: manual
Root-Is-Purelib: false
Tag: cp311-cp311-linux_x86_64
EOF
```

## 9. Run tests (without Playwright)

Playwright browsers cannot be downloaded in the sandbox
(cdn.playwright.dev is not whitelisted). Run tests excluding
Playwright tests:

```bash
uv run pytest -m "not playwright" --maxfail 50
```

**Known sandbox-specific test failures** (not real bugs):
- Tests using VCR cassettes for external APIs (CrossRef,
  DOI) fail because the egress proxy changes the host/port
  in requests. These tests pass on a normal machine.
- Affected test files:
  - `src/bpp/tests/test_admin/test_crossref_api_helpers.py`
  - `src/bpp/tests/test_admin/test_crossref_api_sync.py`
  - `src/importer_publikacji/tests/test_views.py`
  - `src/pbn_import/tests/test_admin_compression.py`

**Note:** Docker builds (`make build`, `docker compose up`)
do not work in the sandbox because Docker image layer CDN
(`*.r2.cloudflarestorage.com`) is not in the proxy allowlist.

**Full test run (without Playwright) takes ~55 minutes** in
the sandbox environment on a single worker.
