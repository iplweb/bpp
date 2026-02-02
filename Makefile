# BPP Makefile
#
# Version Management Workflow:
# ---------------------------
# This project uses CalVer (Calendar Versioning) with the pattern: YYYYMM.BUILD[-TAG[TAGNUM]]
# Example versions: 202510.1274, 202510.1275-dev1, 202510.1275-dev2, 202510.1275
#
# Development Workflow:
#   1. After releasing v202510.1274, start development on next version:
#      make bump-dev
#      This creates: v202510.1275-dev1
#
#   2. During development, build and tag Docker images:
#      docker compose build
#      This tags images as: 202510.1275.dev1 and latest
#
#   3. Ready for release? Remove -dev tag:
#      make bump-release
#      This creates: v202510.1275 (final release version)
#
#   4. Or combine steps 3 and 1 in a single command:
#      make bump-and-start-dev
#      This releases current version and immediately starts next dev cycle
#
# Docker Version:
#   DOCKER_VERSION variable is automatically updated by bumpver
#   Used by both Makefile docker builds and docker-compose.yml
#   Set DOCKER_VERSION environment variable to override for docker-compose

BRANCH=`git branch | sed -n '/\* /s///p'`

.PHONY: clean distclean tests release tests-without-playwright tests-only-playwright docker destroy-test-databases coveralls-upload clean-coverage combine-coverage cache-delete buildx-cache-stats buildx-cache-prune buildx-cache-prune-aggressive buildx-cache-prune-registry buildx-cache-export buildx-cache-import buildx-cache-list bump-dev bump-release bump-and-start-dev migrate new-worktree clean-worktree generate-500-page build build-force build-base build-independent build-app-services build-dbserver build-webserver build-appserver-base build-appserver build-workerserver build-beatserver build-authserver build-denorm-queue build-servers check-clean-tree prepare-claude prepare-developer-machine prepare-developer-machine-linux

PYTHON=python3

# Platform detection for developer machine setup
OS := $(shell uname -s)
ifeq ($(OS),Darwin)
    YARN_CMD := yarn
else
    YARN_CMD := yarnpkg
endif

all:	prepare-developer-machine release

prepare-developer-machine-macos:
	uv sync --all-extras
	brew install cairo pango gdk-pixbuf libffi gobject-introspection gtk+3
	sudo ln -s /opt/homebrew/opt/glib/lib/libgobject-2.0.0.dylib /usr/local/lib/gobject-2.0
	sudo ln -s /opt/homebrew/opt/pango/lib/libpango-1.0.dylib /usr/local/lib/pango-1.0
	sudo ln -s /opt/homebrew/opt/harfbuzz/lib/libharfbuzz.dylib /usr/local/lib/harfbuzz
	sudo ln -s /opt/homebrew/opt/fontconfig/lib/libfontconfig.1.dylib /usr/local/lib/fontconfig-1
	sudo ln -s /opt/homebrew/opt/pango/lib/libpangoft2-1.0.dylib /usr/local/lib/pangoft2-1.0

prepare-developer-machine-linux:
	sudo apt update
	sudo apt install -y yarnpkg python3-dev libpq-dev libcairo2-dev \
		libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev \
		libgirepository1.0-dev libgtk-3-dev
	uv sync --all-extras

prepare-developer-machine:
ifeq ($(OS),Darwin)
	$(MAKE) prepare-developer-machine-macos
else ifeq ($(OS),Linux)
	$(MAKE) prepare-developer-machine-linux
else
	@echo "Unsupported platform: $(OS)"
	@echo "Supported: Darwin (macOS), Linux"
	@exit 1
endif

prepare-claude:
	@echo "Setting up Claude Code with claude-mem plugin..."
	@echo ""
	@echo "NOTE: claude-mem stores memory data locally in ~/.claude/"
	@echo "      Memory data is machine-specific and cannot be shared."
	@echo ""
	@echo "To install claude-mem:"
	@echo "  1. Open Claude Code"
	@echo "  2. Run: /install-plugin thedotmack/claude-mem"
	@echo "  3. Restart Claude Code"
	@echo ""
	@echo "Current installation status:"
	@if [ -d "$$HOME/.claude/plugins/cache/thedotmack/claude-mem" ]; then \
		echo "  claude-mem: INSTALLED"; \
		ls -1 "$$HOME/.claude/plugins/cache/thedotmack/claude-mem" | head -1 | \
			xargs -I{} echo "  Version: {}"; \
	else \
		echo "  claude-mem: NOT INSTALLED"; \
	fi

cleanup-pycs:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rf
	find . -name \*~ -print0 | xargs -0 rm -f
	find . -name \*pyc -print0 | xargs -0 rm -f
	find . -name \*\\.log -print0 | xargs -0 rm -f
	rm -rf build __pycache__ *.log

clean-pycache:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rf
	find . -name \*pyc -print0 | xargs -0 rm -f
	rm -rf .eggs .cache

clean: clean-pycache
	find . -type d -name \*egg-info -print0 | xargs -0 rm -rf
	find . -name \*~ -print0 | xargs -0 rm -f
	find . -name \*.prof -print0 | xargs -0 rm -f
	rm -rf prof/
	find . -name \*\\.log -print0 | xargs -0 rm -f
	find . -name \*\\.log -print0 | xargs -0 rm -f
	find . -name \#\* -print0 | xargs -0 rm -f
	rm -rf build dist/*django_bpp*whl dist/*bpp_iplweb*whl *.log dist
	rm -rf src/django_bpp/staticroot/CACHE
	rm -rf .tox
	rm -rf *xlsx pbn_json_data/

distclean: clean
	rm -rf src/django_bpp/staticroot
	rm -rf *backup .pytest-cache
	rm -rf node_modules src/node_modules src/django_bpp/staticroot
	rm -rf .vagrant splintershots src/components/bower_components src/media
	rm -rf dist
	rm src/bpp/static/scss/*.css
	rm src/bpp/static/scss/*.map


#yarn:
#	export PUPPETEER_SKIP_CHROME_DOWNLOAD=true PUPPETEER_SKIP_CHROME_HEADLESS_SHELL_DOWNLOAD=true && yarn install  --no-progress --emoji false -s

grunt-build:
	grunt build

# CSS output files (targets)
CSS_TARGETS := src/bpp/static/scss/app-blue.css src/bpp/static/scss/app-green.css src/bpp/static/scss/app-orange.css

# SCSS source files
SCSS_SOURCES := $(wildcard src/bpp/static/scss/*.scss)

# Node modules dependency
NODE_MODULES := node_modules/.installed

# Translation files
PO_FILES := $(shell find src -name "*.po" -type f)
MO_FILES := $(PO_FILES:.po=.mo)

$(NODE_MODULES): package.json yarn.lock
	export PUPPETEER_SKIP_CHROME_DOWNLOAD=true PUPPETEER_SKIP_CHROME_HEADLESS_SHELL_DOWNLOAD=true && $(YARN_CMD) install  --no-progress --emoji false -s
	touch $(NODE_MODULES)

$(CSS_TARGETS): $(SCSS_SOURCES) $(NODE_MODULES)
	grunt build

$(MO_FILES): $(PO_FILES)
	# cd src &&  django-admin compilemessages
	uv run python src/manage.py compilemessages --locale=pl --ignore=site-packages

assets: $(CSS_TARGETS) $(MO_FILES)

yarn: $(NODE_MODULES)

production-assets: distclean assets
# usuń ze staticroot niepotrzebne pakiety (Poetry pyproject.toml exclude
# nie do końca to załatwia...)
	rm -rf src/django_bpp/staticroot/{qunit,sinon}
	rm -rf src/django_bpp/staticroot/sitemap-*
	rm -rf src/django_bpp/staticroot/grappelli/tinymce/
	rm -rf src/django_bpp/staticroot/autocomplete_light/vendor/select2/tests/
	rm -rf src/django_bpp/staticroot/vendor/select2/tests/
	rm -rf src/django_bpp/staticroot/rest_framework/docs
	rm -rf src/django_bpp/staticroot/vendor/select2/docs
	rm -rf src/django_bpp/staticroot/scss/*.scss

compilemessages: $(MO_FILES)

# bdist_wheel target removed - no longer using wheel distribution

#upload:
#	twine upload dist/*whl


js-tests: assets
	$(YARN_CMD) install --optional
	npx puppeteer browsers install chrome
	grunt qunit

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs:
	# Nie wrzucam instalacji sphinx-autobuild do requirements_dev.in
	# celowo i z premedytacją:
	uv pip install --upgrade sphinx-autobuild
	uv run sphinx-autobuild --port 8080 -D language=pl docs/ docs/_build

enable-microsoft-auth:
	echo MICROSOFT_AUTH_CLIENT_ID=foobar > ~/.env.local
	echo MICROSOFT_AUTH_CLIENT_SECRET=foobar >> ~/.env.local
	uv pip install django_microsoft_auth

disable-microsoft-auth:
	rm -f ~/.env.local
	uv pip uninstall django_microsoft_auth

clean-coverage:
	rm -f .coverage .coverage.* cov.xml
	rm -rf cov_html

tests-without-playwright:
	uv run pytest -n auto -m "not playwright" --maxfail 50

tests-without-playwright-with-microsoft-auth:
	uv run pytest -n auto -m "not playwright" --maxfail 50

tests-with-microsoft-auth: enable-microsoft-auth tests-without-playwright-with-microsoft-auth disable-microsoft-auth

tests-only-playwright:
	uv run pytest -n auto -m "playwright"

combine-coverage:
	uv run coverage combine
	uv run coverage xml
	uv run coverage html

coveralls-upload:
	uv run coveralls

tests: destroy-test-databases clean-pycache clean-coverage tests-without-playwright tests-only-playwright combine-coverage js-tests coveralls-upload

destroy-test-databases:
	-./bin/drop-test-databases.sh

full-tests: destroy-test-databases clean-coverage tests-with-microsoft-auth destroy-test-databases tests-without-playwright tests-only-playwright js-tests


integration-start-from-match:
	python src/manage.py pbn_integrator --enable-all --start-from-stage=15

integration-start-from-download:
	python src/manage.py pbn_integrator --enable-all --start-from-stage=12

integration-start-from-match-single-thread:
	python src/manage.py pbn_integrator --enable-all --start-from-stage=15 --disable-multiprocessing

restart-pbn-from-download: remove-pbn-integracja-publikacji-dane integration-start-from-download

upgrade-version:
	$(eval CUR_VERSION=v$(shell ./bin/bpp-version.py))
	$(eval NEW_VERSION=$(shell bumpver test $(CUR_VERSION) 'vYYYY0M.BUILD[-TAGNUM]' |head -1|cut -d: -f2))
	git flow release start $(NEW_VERSION)
	uv run bumpver update --commit
	-uv run towncrier build --draft > /tmp/towncrier.txt
	-uv run towncrier build --yes
	-git add uv.lock
	-git commit -F /tmp/towncrier.txt
	@afplay /System/Library/Sounds/Funk.aiff
	GIT_MERGE_AUTOEDIT=no git flow release finish "$(NEW_VERSION)" -p -m "Release $(NEW_VERSION)"

uv-lock:
	uv lock
	-git commit -m "Update lockfile" uv.lock

gh-run-watch:
	gh run watch

gh-run-watch-docker-images:
	gh run watch $$(gh run list --workflow="Docker - oficjalne obrazy" --limit=1 --json databaseId --jq '.[0].databaseId')

gh-run-watch-docker-images-alt:
	gh run list --workflow="Docker - oficjalne obrazy" --limit=1 --json databaseId --jq '.[0].databaseId' | xargs gh run watch

sleep-3:
	sleep 3

generate-500-page:
	uv run python src/manage.py generate_500_page

new-release: uv-lock upgrade-version sleep-3 gh-run-watch-docker-images

check-clean-tree:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working tree is dirty. Commit or stash changes before releasing."; \
		exit 1; \
	fi

release: check-clean-tree full-tests new-release

set-version-from-vcs:
	$(eval CUR_VERSION_VCS=$(shell git describe | sed s/\-/\./ | sed s/\-/\+/))
	bumpver update --no-commit --set-version=$(CUR_VERSION_VCS)

# Version management targets for development workflow
bump-dev:
	@echo "Bumping to next development version..."
	uv run bumpver update --tag dev --tag-num
	@echo "New development version created. Build with: docker compose build"

bump-release:
	@echo "Creating release version (removing -dev tag)..."
	uv run bumpver update --tag final
	@echo "Release version created. You may want to run: make bump-dev"

bump-and-start-dev:
	@echo "Releasing current version and starting next development cycle..."
	uv run bumpver update --tag final
	@echo "Released. Now bumping to next dev version..."
	uv run bumpver update --tag dev --tag-num
	@echo "Ready for development. Build with: docker compose build"

.PHONY: check-git-clean
check-git-clean:
	git diff --quiet

uv-sync:
	uv sync

test-package-from-vcs: check-git-clean uv-sync set-version-from-vcs
	uv build
	ls -lash dist
	git reset --hard

loc: clean
	pygount -N ... -F "...,staticroot,migrations,fixtures" src --format=summary


DOCKER_VERSION=202602.1343

# Cache configuration for docker buildx bake
# - local: use local cache (default for local builds)
# - registry: use Docker Hub registry cache (for CI/CD)
#
# Usage:
#   make build                              # parallel build with local cache
#   DOCKER_CACHE_TYPE=registry make build   # parallel build with registry cache
#   PUSH_TO_REGISTRY=true make build        # build and push to registry
DOCKER_CACHE_TYPE ?= local

# Platform detection: use ARM64 on Apple Silicon, AMD64 otherwise
ARCH := $(shell uname -m)
ifeq ($(ARCH),arm64)
DOCKER_PLATFORM ?= linux/arm64
else
DOCKER_PLATFORM ?= linux/amd64
endif

# Build arguments for docker buildx bake
# Use --file to explicitly use only docker-bake.hcl (avoids merge with docker-compose.yml)
# Variables are passed via environment, platform via --set
# --allow grants filesystem access to cache directory (avoids interactive prompt)
BAKE_ARGS = --file docker-bake.hcl --set '*.platform=$(DOCKER_PLATFORM)' --allow=fs.read=/tmp --allow=fs.write=/tmp

# Export variables for bake (HCL variables read from environment)
export DOCKER_VERSION
export CACHE_TYPE := $(DOCKER_CACHE_TYPE)
# Use environment GIT_SHA if provided (e.g., from CI), otherwise compute from git
GIT_SHA ?= $(shell git rev-parse --short HEAD)
export GIT_SHA

ifeq ($(PUSH_TO_REGISTRY),true)
export PUSH := true
endif

# Main build target - parallel builds using docker buildx bake
# This builds all images in parallel where possible:
# - dbserver, webserver: independent, build immediately
# - base: builds in parallel with above
# - appserver, workerserver, beatserver, authserver, denorm-queue: wait for base
build:
	docker buildx bake $(BAKE_ARGS)

# Force rebuild all images (ignores cache)
build-force:
	docker buildx bake $(BAKE_ARGS) --no-cache

# Build only the base image
build-base:
	docker buildx bake $(BAKE_ARGS) base

# Build independent images only (dbserver + webserver)
build-independent:
	docker buildx bake $(BAKE_ARGS) independent

# Build app services only (requires base image to exist)
build-app-services:
	docker buildx bake $(BAKE_ARGS) app-services

# Individual build targets (for debugging or specific rebuilds)
build-dbserver:
	docker buildx bake $(BAKE_ARGS) dbserver

build-webserver:
	docker buildx bake $(BAKE_ARGS) webserver

build-appserver-base:
	docker buildx bake $(BAKE_ARGS) base

build-appserver:
	docker buildx bake $(BAKE_ARGS) appserver

build-workerserver:
	docker buildx bake $(BAKE_ARGS) workerserver

build-beatserver:
	docker buildx bake $(BAKE_ARGS) beatserver

build-authserver:
	docker buildx bake $(BAKE_ARGS) authserver

build-denorm-queue:
	docker buildx bake $(BAKE_ARGS) denorm-queue

# Alias for backward compatibility
build-servers: build

run-webserver-without-appserver-for-testing: build-webserver
	@echo "Odpalamy webserver wyłącznie, żeby zobaczyć, jak wygląda jego strona błędu..."
	@echo "=============================================================================="
	@echo ""
	@echo http://localhost:10080 and https://localhost:10443
	@echo ""
	@echo "=============================================================================="
	@docker run -d --name appserver --rm alpine sleep infinity &
	@sleep 3
	@docker run --rm -it --link appserver:appserver  -p 10080:80 -p 10443:443 -v ./deploy/webserver/:/etc/ssl/private iplweb/bpp_webserver
	@docker stop -s 9 -t 1 appserver

buildx-cache-stats:
	docker buildx du

buildx-cache-prune:
	docker buildx prune

buildx-cache-prune-aggressive:
	docker buildx prune --keep-storage 5GB

buildx-cache-prune-registry:
	@echo "Note: Registry caches on Docker Hub must be pruned manually."
	@echo "Use 'docker rmi iplweb/bpp_*:cache' to remove local copies of registry caches."

buildx-cache-export:
	@echo "Exporting build cache to local directory..."
	mkdir -p /tmp/docker-buildx-cache-backup
	docker buildx build --cache-to=type=local,dest=/tmp/docker-buildx-cache-backup,mode=max --load --target=scratch -f- . <<< "FROM scratch"

buildx-cache-import:
	@echo "Importing build cache from local directory..."
	if [ -d /tmp/docker-buildx-cache-backup ]; then \
		echo "Cache backup found at /tmp/docker-buildx-cache-backup"; \
	else \
		echo "No cache backup found. Run 'make buildx-cache-export' first."; \
		exit 1; \
	fi

buildx-cache-list:
	@echo "Registry caches on Docker Hub:"
	@echo "  - iplweb/bpp_base:cache"
	@echo "  - iplweb/bpp_appserver:cache"
	@echo "  - iplweb/bpp_workerserver:cache"
	@echo "  - iplweb/bpp_beatserver:cache"
	@echo "  - iplweb/bpp_denorm_queue:cache"
	@echo "  - iplweb/bpp_webserver:cache"
	@echo "  - iplweb/bpp_dbserver:cache"

compose-restart:
	docker compose stop
	docker compose rm -f
	docker compose up --force-recreate

compose-dbshell:
	docker compose exec db /bin/bash


celery-worker-run:
	uv run celery -A django_bpp.celery_tasks worker --pool=threads --concurrency=0

celery-purge:
	DJANGO_SETTINGS_MODULE=django_bpp.settings.local uv run celery -A django_bpp.celery_tasks purge -Q denorm,celery -f

celery-worker-normal:
	uv run celery --app=django_bpp.celery_tasks worker --concurrency=1 --loglevel=INFO  -P solo --without-gossip --without-mingle --without-heartbeat

celery-worker-denorm:
	uv run celery --app=django_bpp.celery_tasks worker -Q denorm --concurrency=1 --loglevel=INFO  -P solo --without-gossip --without-mingle --without-heartbeat

denorm-queue:
	uv run python src/manage.py denorm_queue

migrate:
	uv run python src/manage.py migrate

cache-delete:
	python src/manage.py clear_cache

docker-celery-inspect:
	docker compose exec workerserver-general uv run celery -A django_bpp.celery_tasks inspect active
	docker compose exec workerserver-general uv run celery -A django_bpp.celery_tasks inspect active_queues
	docker compose exec workerserver-general uv run celery -A django_bpp.celery_tasks inspect stats | grep max-concurrency

refresh: build
	docker system prune -f
	docker compose down
	docker compose up -d
	docker system prune -f

remove-denorms:
	echo "DELETE FROM denorm_dirtyinstance;" | uv run python src/manage.py dbshell

clean-docker-cache:
	docker builder prune
	docker builder prune --all
	docker system prune -a --volumes
	rm -rf /tmp/.buildx-cache*

new-worktree:
	./bin/prepare-worktree.sh
	direnv allow
	uv sync --all-extras
	$(YARN_CMD) install
	uv run grunt build
	uv run src/manage.py collectstatic --noinput
	docker compose up -d
	./bin/show-settings.sh

clean-worktree:
	docker compose down -v --remove-orphans

invalidate:
	uv run src/manage.py invalidate all
