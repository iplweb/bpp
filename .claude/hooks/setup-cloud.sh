#!/bin/bash
# SessionStart hook for Claude Code web (cloud sandbox).
# Skipped entirely when running locally (CLI/IDE).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
fi

echo "Cloud sandbox detected — running setup…"

# ── 1. apt over HTTPS (egress proxy workaround) ──────────
sudo sed -i \
  's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' \
  /etc/apt/sources.list.d/ubuntu.sources
sudo sed -i \
  's|http://security.ubuntu.com|https://security.ubuntu.com|g' \
  /etc/apt/sources.list.d/ubuntu.sources
sudo apt-get update -qq

# ── 2. System packages ───────────────────────────────────
sudo apt-get install -y -qq \
  libpq-dev libcairo2-dev libpango1.0-dev \
  libgdk-pixbuf2.0-dev libffi-dev \
  libgirepository1.0-dev libgtk-3-dev \
  libldap2-dev libsasl2-dev python3-dev \
  postgresql-plpython3-16

# ── 3. Polish locale + PostgreSQL restart ─────────────────
sudo locale-gen pl_PL.UTF-8
sudo pg_ctlcluster 16 main restart

# ── 4. PostgreSQL trust auth ──────────────────────────────
PG_HBA=/etc/postgresql/16/main/pg_hba.conf
sudo sed -i \
  's/^local.*all.*all.*peer/local   all   all   trust/' \
  "$PG_HBA"
sudo sed -i \
  's/^host.*all.*all.*127.0.0.1\/32.*scram-sha-256/host    all   all   127.0.0.1\/32   trust/' \
  "$PG_HBA"
sudo pg_ctlcluster 16 main reload

# ── 5. Database ───────────────────────────────────────────
sudo -u postgres psql -c \
  "SELECT 1 FROM pg_roles WHERE rolname='bpp'" \
  | grep -q 1 \
  || sudo -u postgres psql -c \
       "CREATE USER bpp WITH PASSWORD '' SUPERUSER;"
sudo -u postgres psql -tc \
  "SELECT 1 FROM pg_database WHERE datname='bpp'" \
  | grep -q 1 \
  || sudo -u postgres psql -c \
       "CREATE DATABASE bpp OWNER bpp;"

# ── 6. Redis ──────────────────────────────────────────────
redis-cli ping >/dev/null 2>&1 \
  || redis-server --daemonize yes

# ── 7. .env ───────────────────────────────────────────────
if [ ! -f "$CLAUDE_PROJECT_DIR/.env" ]; then
cat > "$CLAUDE_PROJECT_DIR/.env" << 'DOTENV'
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
DOTENV
fi

# ── 8. Python dependencies ────────────────────────────────
cd "$CLAUDE_PROJECT_DIR"
uv sync --all-extras || true

# psycopg2 workaround: install binary, fake dist-info
if ! python -c "import psycopg2" 2>/dev/null; then
    uv pip install psycopg2-binary==2.9.11
    SITE_PKG=$(.venv/bin/python -c \
      "import site; print(site.getsitepackages()[0])")
    mkdir -p "$SITE_PKG/psycopg2-2.9.11.dist-info"
    cat > "$SITE_PKG/psycopg2-2.9.11.dist-info/METADATA" \
      << 'META'
Metadata-Version: 2.1
Name: psycopg2
Version: 2.9.11
META
    cat > "$SITE_PKG/psycopg2-2.9.11.dist-info/RECORD" \
      << 'REC'
psycopg2/__init__.py,sha256=,
psycopg2-2.9.11.dist-info/METADATA,sha256=,
psycopg2-2.9.11.dist-info/RECORD,,
REC
    echo "uv" > \
      "$SITE_PKG/psycopg2-2.9.11.dist-info/INSTALLER"
    cat > "$SITE_PKG/psycopg2-2.9.11.dist-info/WHEEL" \
      << 'WHL'
Wheel-Version: 1.0
Generator: manual
Root-Is-Purelib: false
Tag: cp311-cp311-linux_x86_64
WHL
fi

echo "Cloud setup complete."
