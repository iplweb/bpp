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

.PHONY: clean distclean tests release tests-without-playwright tests-only-playwright docker destroy-test-databases coveralls-upload clean-coverage combine-coverage cache-delete buildx-cache-stats buildx-cache-prune buildx-cache-prune-aggressive buildx-cache-prune-registry buildx-cache-export buildx-cache-import buildx-cache-list bump-dev bump-release bump-and-start-dev migrate new-worktree clean-worktree generate-500-page build-denorm-queue build-authserver

PYTHON=python3

all:	prepare-developer-machine-macos release

prepare-developer-machine-macos:
	uv sync --all-extras
	brew install cairo pango gdk-pixbuf libffi gobject-introspection gtk+3
	sudo ln -s /opt/homebrew/opt/glib/lib/libgobject-2.0.0.dylib /usr/local/lib/gobject-2.0
	sudo ln -s /opt/homebrew/opt/pango/lib/libpango-1.0.dylib /usr/local/lib/pango-1.0
	sudo ln -s /opt/homebrew/opt/harfbuzz/lib/libharfbuzz.dylib /usr/local/lib/harfbuzz
	sudo ln -s /opt/homebrew/opt/fontconfig/lib/libfontconfig.1.dylib /usr/local/lib/fontconfig-1
	sudo ln -s /opt/homebrew/opt/pango/lib/libpangoft2-1.0.dylib /usr/local/lib/pangoft2-1.0

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
	export PUPPETEER_SKIP_CHROME_DOWNLOAD=true PUPPETEER_SKIP_CHROME_HEADLESS_SHELL_DOWNLOAD=true && yarn install  --no-progress --emoji false -s
	touch $(NODE_MODULES)

$(CSS_TARGETS): $(SCSS_SOURCES) $(NODE_MODULES)
	grunt build

$(MO_FILES): $(PO_FILES)
	# cd src &&  django-admin compilemessages
	python src/manage.py compilemessages --locale=pl --ignore=site-packages

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
	yarn install --optional
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
	uv pip uninstall -y django_microsoft_auth

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

tests: destroy-test-databases clean-coverage tests-without-playwright tests-only-playwright combine-coverage js-tests coveralls-upload

destroy-test-databases:
	-./bin/drop-test-databases.sh

full-tests: destroy-test-databases clean-coverage tests-with-microsoft-auth destroy-test-databases tests-without-playwright tests-only-playwright combine-coverage js-tests coveralls-upload


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

release: full-tests new-release

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


DOCKER_VERSION="202601.1314"

DOCKER_BUILD=build --platform linux/amd64 --push
#--no-cache


# Na lokalnej maszynie nie uzywaj --push + buduj tylko ARM + uzywaj docker driver
HOST="$(shell hostname)"
ifeq (${HOST},"swift-beast.local")
DOCKER_BUILD=build --builder desktop-linux --platform linux/arm64 --load
endif

# Cache configuration - use DOCKER_CACHE_TYPE environment variable
# - local: use local cache only (default for local builds)
#   Cache is stored in /tmp/.buildx-cache-* directories
# - registry: use Docker Hub registry cache (for CI/CD)
#   Cache is stored as iplweb/bpp_*:cache images on Docker Hub
#
# Usage:
#   make build                           # uses local cache (default)
#   DOCKER_CACHE_TYPE=local make build  # explicit local cache
#   DOCKER_CACHE_TYPE=registry make build  # use Docker Hub cache
DOCKER_CACHE_TYPE ?= local

ifeq ($(DOCKER_CACHE_TYPE),registry)
CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_base:latest
CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_base:cache,mode=max
else
CACHE_FROM=
CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache,mode=max
endif

CACHE_FLAGS=$(CACHE_FROM) $(CACHE_TO)

ifeq ($(DOCKER_CACHE_TYPE),registry)
DBSERVER_CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_dbserver:latest
DBSERVER_CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_dbserver:cache,mode=max
APPSERVER_CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_appserver:latest
APPSERVER_CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_appserver:cache,mode=max
WORKERSERVER_CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_workerserver:latest
WORKERSERVER_CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_workerserver:cache,mode=max
WEBSERVER_CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_webserver:latest
WEBSERVER_CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_webserver:cache,mode=max
DENORM_QUEUE_CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_denorm_queue:latest
DENORM_QUEUE_CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_denorm_queue:cache,mode=max
BEATSERVER_CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_beatserver:latest
BEATSERVER_CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_beatserver:cache,mode=max
AUTHSERVER_CACHE_FROM=--cache-from=type=registry,ref=iplweb/bpp_authserver:latest
AUTHSERVER_CACHE_TO=--cache-to=type=registry,ref=iplweb/bpp_authserver:cache,mode=max
else
DBSERVER_CACHE_FROM=
DBSERVER_CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache-dbserver,mode=max
APPSERVER_CACHE_FROM=
APPSERVER_CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache-appserver,mode=max
WORKERSERVER_CACHE_FROM=
WORKERSERVER_CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache-workerserver,mode=max
WEBSERVER_CACHE_FROM=
WEBSERVER_CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache-webserver,mode=max
DENORM_QUEUE_CACHE_FROM=
DENORM_QUEUE_CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache-denorm-queue,mode=max
BEATSERVER_CACHE_FROM=
BEATSERVER_CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache-beatserver,mode=max
AUTHSERVER_CACHE_FROM=
AUTHSERVER_CACHE_TO=--cache-to=type=local,dest=/tmp/.buildx-cache-authserver,mode=max
endif

build-dbserver: deploy/dbserver/Dockerfile deploy/dbserver/autotune.py deploy/dbserver/docker-entrypoint-autotune.sh
	docker buildx ${DOCKER_BUILD} ${DBSERVER_CACHE_FROM} ${DBSERVER_CACHE_TO} -t iplweb/bpp_dbserver:${DOCKER_VERSION} -t iplweb/bpp_dbserver:latest -f deploy/dbserver/Dockerfile deploy/dbserver/

build-appserver-base:
	docker buildx ${DOCKER_BUILD} ${CACHE_FLAGS} -t iplweb/bpp_base:${DOCKER_VERSION} -t iplweb/bpp_base:latest -f deploy/bpp_base/Dockerfile .

build-appserver: build-appserver-base
	docker buildx ${DOCKER_BUILD} ${CACHE_FROM} ${APPSERVER_CACHE_FROM} ${APPSERVER_CACHE_TO} -t iplweb/bpp_appserver:${DOCKER_VERSION} -t iplweb/bpp_appserver:latest -f deploy/appserver/Dockerfile .

build-workerserver: build-appserver-base
	docker buildx ${DOCKER_BUILD} ${CACHE_FROM} ${WORKERSERVER_CACHE_FROM} ${WORKERSERVER_CACHE_TO} -t iplweb/bpp_workerserver:${DOCKER_VERSION} -t iplweb/bpp_workerserver:latest -f deploy/workerserver/Dockerfile .

build-webserver: deploy/webserver/Dockerfile deploy/webserver/default.conf.template deploy/webserver/maintenance.html deploy/webserver/key.pem deploy/webserver/cert.pem
	docker buildx ${DOCKER_BUILD} ${WEBSERVER_CACHE_FROM} ${WEBSERVER_CACHE_TO} -t iplweb/bpp_webserver:${DOCKER_VERSION} -t iplweb/bpp_webserver:latest -f deploy/webserver/Dockerfile deploy/webserver/

build-denorm-queue: deploy/denorm-queue/Dockerfile deploy/denorm-queue/entrypoint-denorm-queue.sh
	docker buildx ${DOCKER_BUILD} ${CACHE_FROM} ${DENORM_QUEUE_CACHE_FROM} ${DENORM_QUEUE_CACHE_TO} -t iplweb/bpp_denorm_queue:${DOCKER_VERSION} -t iplweb/bpp_denorm_queue:latest -f deploy/denorm-queue/Dockerfile .

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

build-beatserver: build-appserver-base
	docker buildx ${DOCKER_BUILD} ${CACHE_FROM} ${BEATSERVER_CACHE_FROM} ${BEATSERVER_CACHE_TO} -t iplweb/bpp_beatserver:${DOCKER_VERSION} -t iplweb/bpp_beatserver:latest -f deploy/beatserver/Dockerfile deploy/beatserver/

build-authserver: build-appserver-base deploy/authserver/Dockerfile deploy/authserver/entrypoint-authserver.sh
	docker buildx ${DOCKER_BUILD} ${CACHE_FROM} ${AUTHSERVER_CACHE_FROM} ${AUTHSERVER_CACHE_TO} -t iplweb/bpp_authserver:${DOCKER_VERSION} -t iplweb/bpp_authserver:latest -f deploy/authserver/Dockerfile .

#build-flower:
#	docker buildx ${DOCKER_BUILD} -t iplweb/flower:${DOCKER_VERSION} -t iplweb/flower:latest -f deploy/flower/Dockerfile deploy/flower/

build-servers: build-appserver-base build-appserver build-workerserver build-beatserver build-authserver build-denorm-queue # build-flower

build: build-dbserver build-webserver build-servers

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
	yarn install
	uv run grunt build
	uv run src/manage.py collectstatic --noinput
	docker compose up -d
	./bin/show-settings.sh

clean-worktree:
	docker compose down -v --remove-orphans
