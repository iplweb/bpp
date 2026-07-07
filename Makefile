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

.PHONY: help clean distclean tests test-durations release tests-without-playwright tests-only-playwright docker destroy-test-databases cache-delete buildx-cache-stats buildx-cache-prune buildx-cache-prune-aggressive buildx-cache-prune-registry buildx-cache-export buildx-cache-import buildx-cache-list bump-dev bump-release bump-and-start-dev migrate new-worktree clean-worktree generate-500-page build build-force build-base build-app-services build-appserver-base build-appserver build-workerserver build-beatserver build-authserver build-denorm-queue build-servers docker-images-on-ci check-clean-tree prepare-claude prepare-developer-machine prepare-developer-machine-linux prepare-developer-machine-macos playwright-install

.DEFAULT_GOAL := help

##@ Pomoc

help: ## Wyświetl tę listę celów
	@awk 'BEGIN {FS = ":.*?## "; \
		printf "\nUżycie:\n  make \033[36m<cel>\033[0m\n"} \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z_][a-zA-Z0-9_-]*:.*?## / { \
			printf "  \033[36m%-32s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

PYTHON=python3

# Platform detection for developer machine setup
OS := $(shell uname -s)
ifeq ($(OS),Darwin)
    YARN_CMD := yarn
else
    YARN_CMD := yarnpkg
endif

##@ Konfiguracja maszyny deweloperskiej

all:	prepare-developer-machine release ## UWAGA: pełna konfiguracja + release (uruchamia release!)

# WeasyPrint (cffi.dlopen / ctypes.util.find_library) musi znalezc
# libgobject-2.0 / pango / harfbuzz / fontconfig zainstalowane przez brew.
# Na Apple Silicon te biblioteki siedza w /opt/homebrew/lib, ktorego dyld
# nie konsultuje domyslnie (default search path to /usr/local/lib + /usr/lib).
#
# Probowalismy wczesniej (commit 3531fd2d4) DYLD_FALLBACK_LIBRARY_PATH —
# nie sprawdza sie w praktyce: macOS SIP strippuje wszystkie zmienne DYLD_*
# w momencie wywolania chronionej binarki (/usr/bin/*, /bin/sh, itp.), wiec
# w lancuchach typu  make → sh → uv → python → pytest  zmienna regularnie
# ginie po drodze. Z perspektywy pytest/uv vs. dlopen — niedeterministyczne.
#
# Wracamy do symlinkow w /usr/local/lib: filesystem-level, dyld konsultuje
# te sciezke z automatu, SIP nic z tym nie zrobi. Wymaga sudo *raz*
# przy setupie maszyny. Idempotent — recipe nie nadpisuje istniejacych
# symlinkow wskazujacych na te same cele.
#
# UWAGA: To runtime fix dla dlopen. Nie pomaga przy *build-time* bledach
# (np. wheel buduje sie z zrodla i nie znajduje cairo.h) — wtedy potrzeba
# PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig + LDFLAGS=-L/opt/homebrew/lib
# + CPPFLAGS=-I/opt/homebrew/include.
prepare-developer-machine-macos: ## Zainstaluj zależności systemowe na macOS (brew + uv sync + playwright + symlinki)
	@if ! command -v brew >/dev/null 2>&1; then \
		echo ""; \
		echo "BŁĄD: Homebrew (brew) nie jest zainstalowany."; \
		echo ""; \
		echo "Homebrew jest wymagany do zainstalowania zależności systemowych"; \
		echo "(cairo, pango, gdk-pixbuf, libffi, gobject-introspection, gtk+3)."; \
		echo ""; \
		echo "Aby zainstalować Homebrew, uruchom w terminalu poniższe polecenie:"; \
		echo ""; \
		echo '  /bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'; \
		echo ""; \
		echo "Po zakończeniu instalacji wykonaj kroki dodające 'brew' do PATH"; \
		echo "wypisane przez instalator (zwykle dla Apple Silicon: dopisanie"; \
		echo "linii 'eval \"\$$(/opt/homebrew/bin/brew shellenv)\"' do ~/.zprofile)."; \
		echo ""; \
		echo "Pełna dokumentacja: https://brew.sh"; \
		echo ""; \
		echo "Po instalacji Homebrew uruchom ponownie:  make prepare-developer-machine"; \
		echo ""; \
		exit 1; \
	fi
	brew install cairo pango gdk-pixbuf libffi gobject-introspection gtk+3 node yarn
	npm install -g grunt-cli
	uv sync --frozen --no-install-project --all-extras
	@# Symlinki w /usr/local/lib — dyld konsultuje te sciezke domyslnie,
	@# wiec niezaleznie od stanu DYLD_* (SIP) WeasyPrint znajdzie libki.
	@if [ ! -d /usr/local/lib ]; then \
		echo "Tworze /usr/local/lib (wymagane sudo)..."; \
		sudo mkdir -p /usr/local/lib; \
	fi
	@for pair in \
		"/opt/homebrew/opt/glib/lib/libgobject-2.0.0.dylib:gobject-2.0" \
		"/opt/homebrew/opt/pango/lib/libpango-1.0.dylib:pango-1.0" \
		"/opt/homebrew/opt/harfbuzz/lib/libharfbuzz.dylib:harfbuzz" \
		"/opt/homebrew/opt/fontconfig/lib/libfontconfig.1.dylib:fontconfig-1" \
		"/opt/homebrew/opt/pango/lib/libpangoft2-1.0.dylib:pangoft2-1.0"; do \
		src="$${pair%:*}"; dst="/usr/local/lib/$${pair##*:}"; \
		if [ -L "$$dst" ] && [ "$$(readlink "$$dst")" = "$$src" ]; then \
			echo "Symlink $$dst juz wskazuje na $$src — pomijam."; \
		else \
			echo "Tworze symlink $$dst -> $$src (wymagane sudo)..."; \
			sudo ln -sf "$$src" "$$dst"; \
		fi; \
	done
	@# Cleanup po poprzedniej probie z DYLD_FALLBACK_LIBRARY_PATH —
	@# usun marker + linie export z ~/.zprofile, jesli zostaly.
	@ZPROFILE="$$HOME/.zprofile"; \
	MARKER='# bpp: weasyprint dlopen (Homebrew libs on Apple Silicon)'; \
	if [ -f "$$ZPROFILE" ] && grep -qF "$$MARKER" "$$ZPROFILE"; then \
		cp "$$ZPROFILE" "$$ZPROFILE.bpp-bak"; \
		awk -v m="$$MARKER" 'BEGIN{skip=0} \
			$$0==m {skip=1; next} \
			skip>0 {skip--; next} \
			{print}' "$$ZPROFILE.bpp-bak" > "$$ZPROFILE"; \
		echo "Usunieto stary wpis DYLD_FALLBACK_LIBRARY_PATH z $$ZPROFILE (backup: $$ZPROFILE.bpp-bak)."; \
	fi
	$(MAKE) playwright-install

prepare-developer-machine-linux: ## Zainstaluj zależności systemowe na Linuksie (apt + uv sync + playwright)
	sudo apt update
	sudo apt install -y yarnpkg nodejs npm python3-dev libpq-dev \
		libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev \
		libgirepository1.0-dev libgtk-3-dev
	sudo npm install -g grunt-cli
	uv sync --frozen --no-install-project --all-extras
	$(MAKE) playwright-install

prepare-developer-machine: ## Zainstaluj zależności systemowe (auto-detekcja macOS/Linux)
ifeq ($(OS),Darwin)
	$(MAKE) prepare-developer-machine-macos
else ifeq ($(OS),Linux)
	$(MAKE) prepare-developer-machine-linux
else
	@echo "Unsupported platform: $(OS)"
	@echo "Supported: Darwin (macOS), Linux"
	@exit 1
endif

# Pobiera przeglądarki Playwright (chromium itd.) potrzebne do testów E2E.
# Na Linuksie używa --with-deps, żeby playwright doinstalował systemowe
# biblioteki (libnss3, libatk, libgtk-3...) przez apt — to wymaga sudo
# i jest dokładnie tym, co opisuje README sekcja 2 ("uv run playwright
# install" + "sudo playwright install-deps") tylko sklejone w jednej
# komendzie. Na macOS install-deps to no-op (browsers są self-contained,
# a brew już zainstalował systemowe libki w prepare-developer-machine-macos),
# więc używamy gołego "playwright install".
#
# Wymaga, by uv sync --all-extras zostało wcześniej wykonane (playwright
# CLI siedzi w grupie dev pyproject.toml). Stąd kolejność w prepare-*.
playwright-install: ## Pobierz przeglądarki Playwright dla testów E2E (na Linuksie z --with-deps, sudo)
ifeq ($(OS),Darwin)
	uv run playwright install
else
	uv run playwright install --with-deps
endif

prepare-claude: ## Pokaż instrukcję instalacji wtyczki claude-mem w Claude Code
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

##@ Czyszczenie

cleanup-pycs: ## Usuń __pycache__, *.pyc, *.log i pliki tymczasowe
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rf
	find . -name \*~ -print0 | xargs -0 rm -f
	find . -name \*pyc -print0 | xargs -0 rm -f
	find . -name \*\\.log -print0 | xargs -0 rm -f
	rm -rf build __pycache__ *.log

clean-pycache: ## Usuń __pycache__, *.pyc oraz .eggs/.cache
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rf
	find . -name \*pyc -print0 | xargs -0 rm -f
	rm -rf .eggs .cache

clean: clean-pycache ## Szersze czyszczenie: egg-info, logi, build, dist, staticroot/CACHE, .tox
	rm -f .grunt-build-stamp
	find . -type d -name \*egg-info -print0 | xargs -0 rm -rf
	find . -name \*~ -print0 | xargs -0 rm -f
	find . -name \*.prof -print0 | xargs -0 rm -f
	rm -rf prof/
	find . -name \*\\.log -print0 | xargs -0 rm -f
	find . -name \#\* -not -path './node_modules/*' -print0 | xargs -0 rm -rf
	rm -rf build dist/*django_bpp*whl dist/*bpp_iplweb*whl *.log dist
	rm -rf src/django_bpp/staticroot/CACHE
	rm -rf .tox
	rm -rf *xlsx pbn_json_data/

distclean: clean ## Pełne czyszczenie: + node_modules, staticroot, media, dist, skompilowane CSS
	rm -rf src/django_bpp/staticroot
	rm -rf *backup .pytest-cache
	rm -rf node_modules src/node_modules src/django_bpp/staticroot
	rm -rf .vagrant src/components/bower_components src/media
	rm -rf dist
	rm src/bpp/static/scss/*.css
	rm src/bpp/static/scss/*.map


#yarn:
#	export PUPPETEER_SKIP_CHROME_DOWNLOAD=true PUPPETEER_SKIP_CHROME_HEADLESS_SHELL_DOWNLOAD=true && yarn install  --no-progress --emoji false -s

##@ Frontend / Assety

grunt-build: ## Uruchom `grunt build` (SCSS → CSS, bundling JS)
	grunt build

# grunt build kompiluje WSZYSTKIE SCSS → CSS za jednym odpaleniem.
# Pattern rule $(CSS_TARGETS): $(SCSS_SOURCES) odpalałby grunt N razy
# (raz per out-of-date target). Zamiast tego: jeden stamp file zależy od
# wszystkich SCSS + node_modules; grunt dotyka stampu po zakończeniu.

SCSS_SOURCES := $(wildcard src/bpp/static/scss/*.scss) \
                $(wildcard src/*/static/*/scss/*.scss)

# Źródła JS bundlowane przez `grunt build` (esbuild: główny bundle + cytoscape
# eksploratora powiązań). Stamp musi zależeć też od nich, inaczej zmiana w JS
# (np. src/powiazania_autorow/.../js/powiazania/*.js) nie odpala przebudowy i
# serwowany jest stary bundle. `*.js` NIE schodzi do podkatalogu dist/, więc
# wygenerowane bundle nie stają się własną zależnością (brak pętli rebuildu).
JS_SOURCES := $(wildcard src/bpp/static/bpp/js/*.js) \
              $(wildcard src/powiazania_autorow/static/powiazania_autorow/js/*.js) \
              $(wildcard src/powiazania_autorow/static/powiazania_autorow/js/powiazania/*.js) \
              $(wildcard src/powiazania_autorow/static/powiazania_autorow/js/siec3d/*.js)

# Node modules dependency
NODE_MODULES := node_modules/.installed

# Translation files
PO_FILES := $(shell find src -name "*.po" -type f)
MO_FILES := $(PO_FILES:.po=.mo)

$(NODE_MODULES): package.json yarn.lock
	export PUPPETEER_SKIP_CHROME_DOWNLOAD=true PUPPETEER_SKIP_CHROME_HEADLESS_SHELL_DOWNLOAD=true && $(YARN_CMD) install  --no-progress --emoji false -s
	touch $(NODE_MODULES)

CSS_STAMP := .grunt-build-stamp

$(CSS_STAMP): $(SCSS_SOURCES) $(JS_SOURCES) $(NODE_MODULES)
	grunt build
	@touch $(CSS_STAMP)

$(MO_FILES): $(PO_FILES)
	uv run python src/manage.py compilemessages --locale=pl --ignore=site-packages

assets: $(CSS_STAMP) $(MO_FILES) ## Zbuduj frontend (CSS + .mo); uruchamia `yarn install` jeśli trzeba

yarn: $(NODE_MODULES) ## Zainstaluj zależności Node.js (yarn install)

production-assets: distclean assets ## Pełny clean + build assetów pod produkcję
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

compilemessages: $(MO_FILES) ## Skompiluj tłumaczenia Django (*.po → *.mo)

# bdist_wheel target removed - no longer using wheel distribution

#upload:
#	twine upload dist/*whl


js-tests: ## Jednostkowe testy JS (vitest): czysta logika modułów BPP
	$(YARN_CMD) install --frozen-lockfile
	npx vitest run

##@ Dokumentacja

# cel: live-docs
# Uruchom mkdocs serve (live-reload docs)
live-docs: ## Uruchom mkdocs serve na porcie 8080 (live-reload docs)
	# Zaleznosci docsow trzymamy poza glownym dev-extras (uzywane tylko
	# lokalnie i na Read the Docs) — instalujemy ad-hoc:
	uv pip install -r docs/requirements.txt
	uv run mkdocs serve --dev-addr 127.0.0.1:8080

##@ Microsoft Auth

enable-microsoft-auth: ## Włącz django_microsoft_auth (dla testów integracyjnych)
	echo MICROSOFT_AUTH_CLIENT_ID=foobar > ~/.env.local
	echo MICROSOFT_AUTH_CLIENT_SECRET=foobar >> ~/.env.local
	uv pip install django_microsoft_auth

disable-microsoft-auth: ## Wyłącz django_microsoft_auth
	rm -f ~/.env.local
	uv pip uninstall django_microsoft_auth

##@ Testy

# pytest-split czyta `.test_durations` (commitowany), zeby CI dzielilo
# suite na grupy o ~rownym CZASIE (a nie liczbie testow). Plik odswiezamy
# lokalnie: gdy STORE_DURATIONS=1, oba przebiegi ponizej dopisuja swoje
# czasy do `.test_durations`. pytest-split MERGE'uje (bez --clean-durations
# zaden przebieg nie kasuje testow drugiego), wiec `not playwright` +
# `playwright` skladaja sie na komplet. Domyslnie OFF — szybka iteracja
# (`make tests-without-playwright`) nie brudzi pliku. `make tests` i
# `make test-durations` wlaczaja zapis przez target-specific STORE_DURATIONS.
STORE_DURATIONS ?=
_store_durations = $(if $(STORE_DURATIONS),--store-durations --durations-path .test_durations,)
# Po zapisie zaokraglij+posortuj plik (maly, stabilny diff). `&&` —
# normalizujemy tylko po udanym przebiegu; przy STORE_DURATIONS pustym
# rozwija sie do `true` (no-op).
_normalize_durations = $(if $(STORE_DURATIONS),&& uv run python bin/normalize_test_durations.py,)

tests-without-playwright: ## Szybkie testy bez Playwright (xdist -n auto, maxfail=50)
	uv run pytest -n auto -m "not playwright" --maxfail 50 $(_store_durations) $(_normalize_durations)

tests-without-playwright-with-microsoft-auth: ## tests-without-playwright z aktywnym Microsoft Auth
	uv run pytest -n auto -m "not playwright" --maxfail 50

tests-with-microsoft-auth: enable-microsoft-auth tests-without-playwright-with-microsoft-auth disable-microsoft-auth ## Włącz MS Auth, uruchom testy, wyłącz

tests-only-playwright: playwright-install ## Tylko testy Playwright (wolne)
	uv run pytest -n auto -m "playwright" $(_store_durations) $(_normalize_durations)

uv-sync: ## uv sync --all-extras (synchronizacja zależności Pythona)
	uv sync --no-install-project --all-extras

# Target-specific STORE_DURATIONS=1 jest dziedziczone przez prerekwizyty
# (GNU Make), wiec pelny `make tests` odswieza `.test_durations` przy okazji
# (oba przebiegi dopisuja, pytest-split merge'uje). Standalone
# `make tests-without-playwright` pozostaje OFF — bez churnu w pliku.
tests: STORE_DURATIONS = 1
tests: clean-pycache uv-sync tests-without-playwright tests-only-playwright js-tests ## Pełny test suite (Playwright + JS) + odśwież .test_durations

# Sam regen `.test_durations` bez js-tests — pelny przebieg pytest (oba
# markery) z zapisem czasow. Uzyj gdy chcesz tylko odswiezyc plik splitu
# CI (np. po dodaniu wolnych testow) bez reszty `make tests`.
test-durations: STORE_DURATIONS = 1
test-durations: clean-pycache uv-sync tests-without-playwright tests-only-playwright ## Regeneruj .test_durations (split CI), bez js-tests

# Wygeneruj raport pokrycia w formacie zoptymalizowanym pod AI/LLM:
# sortowany od najgorszego, z zakresami linii missing, bez śmieci
# (migrations, tests, __init__.py). Wyjście leci na stdout — agent pipuje
# do swojego kontekstu albo zapisuje (`make coverage-ai > /tmp/cov.txt`).
# Domyślnie pomija playwright (długie). Override: COVERAGE_PYTEST_ARGS='-m ""'.
COVERAGE_PYTEST_ARGS ?= -m "not playwright"
COVERAGE_THRESHOLD ?= 90
COVERAGE_LIMIT ?= 30

coverage-ai: ## Raport pokrycia dla AI (sortowane ascending, top N najgorszych)
	@rm -f .coverage .coverage.* coverage.json
	uv run pytest -n auto $(COVERAGE_PYTEST_ARGS) \
		--cov=src --cov-branch --cov-report=
	uv run coverage json -o coverage.json --quiet
	@echo ""
	@uv run python bin/coverage_for_ai.py \
		--threshold $(COVERAGE_THRESHOLD) \
		--limit $(COVERAGE_LIMIT)

# Same as `tests` but forces a full DB rebuild from scratch instead of
# reusing the schema produced by the baseline + delta migrate. Use when
# you suspect schema corruption or need to validate migrations from zero.
tests-fresh: destroy-test-databases tests ## Jak `tests`, ale od zera (destroy-test-databases + tests)

# Regenerate baseline-sql/baseline.sql by spinning up an isolated
# postgres (via testcontainers), running migrate, dumping, and writing
# baseline.meta.json. Commit the refreshed files to git.
rebuild-baseline: ## Regeneruj baseline.sql OD ZERA (pełny reset; duży diff)
	DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py baseline_rebuild
	@echo ""
	@echo "Baseline regenerated. Files:"
	@ls -lh baseline-sql/baseline.sql baseline-sql/baseline.meta.json
	@echo ""
	@echo "Don't forget to commit:"
	@echo "    git add baseline-sql/baseline.sql baseline-sql/baseline.meta.json"

# Update baseline-sql/baseline.sql IN PLACE: load the existing baseline
# into an isolated postgres, apply pending migrations, dump back. Preserves
# auto-increment IDs and the existing dump representation, so the diff is
# just the delta of the new migrations -- no full auth/* table churn (column
# reordering, IDENTITY-vs-serial) that the from-scratch `rebuild-baseline`
# produces. This is the usual way to refresh the baseline after adding
# migrations; reach for `rebuild-baseline` only for a full reset.
baseline-update: ## Zaktualizuj baseline.sql IN-PLACE (load+migrate+dump; mały diff)
	DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py baseline_update
	@echo ""
	@echo "Baseline updated in place. Files:"
	@ls -lh baseline-sql/baseline.sql baseline-sql/baseline.meta.json
	@echo ""
	@echo "Don't forget to commit:"
	@echo "    git add baseline-sql/baseline.sql baseline-sql/baseline.meta.json"

# Run tests against pre-existing docker-compose containers (no testcontainers).
tests-no-containers: ## Testy przeciwko istniejącym kontenerom docker-compose (bez testcontainers)
	uv run pytest --no-testcontainers -n auto -m "not playwright" --maxfail 50

# Stop reusable testcontainers (bpp-tc-pg, bpp-tc-redis).
tests-stop-containers: ## Zatrzymaj i usuń reużywalne testcontainers (bpp-tc-*)
	-docker stop bpp-tc-pg bpp-tc-redis 2>/dev/null
	-docker rm bpp-tc-pg bpp-tc-redis 2>/dev/null
	@echo "Testcontainers stopped and removed."

# Remove ALL orphaned testcontainers (including Ryuks from crashed pytest runs).
clean-testcontainers: ## Usuń wszystkie osierocone testcontainers (PG/Redis/Ryuk + reuse bpp-tc-*)
	@echo "Removing all containers labeled org.testcontainers=true ..."
	-@docker ps -aq --filter "label=org.testcontainers=true" | xargs -r docker rm -f
	-@docker rm -f bpp-tc-pg bpp-tc-redis 2>/dev/null || true
	@echo "Done."

# Run tests with ephemeral containers (destroyed after run).
tests-ephemeral: ## Testy w efemerycznych testcontainers (usuwane po teście)
	PYTEST_TESTCONTAINERS_REUSE=0 uv run pytest -n auto -m "not playwright" --maxfail 50

tests-in-docker: ## Testy w pełni w Dockerze (docker-compose.test.yml)
	docker compose -f docker-compose.test.yml build test-runner
	docker compose -f docker-compose.test.yml up -d db redis
	docker compose -f docker-compose.test.yml run --rm test-runner \
		uv run pytest -n auto -m "not playwright" --maxfail 50
	docker compose -f docker-compose.test.yml down

tests-in-docker-interactive: ## tests-in-docker z interaktywnym bashem w kontenerze
	docker compose -f docker-compose.test.yml build test-runner
	docker compose -f docker-compose.test.yml up -d db redis
	docker compose -f docker-compose.test.yml run --rm test-runner bash

tests-in-docker-down: ## Zatrzymaj i usuń środowisko tests-in-docker (wraz z volume)
	docker compose -f docker-compose.test.yml down -v

destroy-test-databases: ## Drop wszystkich baz testowych (local Postgres)
	-./bin/drop-test-databases.sh

full-tests: destroy-test-databases tests-with-microsoft-auth destroy-test-databases tests-without-playwright tests-only-playwright js-tests ## Ekstremalnie pełny test suite (drop DB + MS Auth + Playwright + JS)


##@ PBN — integracja

integration-start-from-match: ## PBN integrator od etapu 15 (matching)
	python src/manage.py pbn_integrator --enable-all --start-from-stage=15

integration-start-from-download: ## PBN integrator od etapu 12 (pobieranie)
	python src/manage.py pbn_integrator --enable-all --start-from-stage=12

integration-start-from-match-single-thread: ## integration-start-from-match bez multiprocessingu
	python src/manage.py pbn_integrator --enable-all --start-from-stage=15 --disable-multiprocessing

restart-pbn-from-download: remove-pbn-integracja-publikacji-dane integration-start-from-download ## Wymaż dane integracji i zacznij od pobierania

##@ Wersjonowanie i release

upgrade-version: ## git-flow release + bumpver + towncrier (podbij wersję i zamknij release branch)
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

uv-lock: ## uv lock + commit uv.lock
	uv lock
	-git commit -m "Update lockfile" uv.lock

# Defense-in-depth do Dependabot cooldown (.github/dependabot.yml). Gdy
# manualnie odpalasz `uv lock` (np. po dodaniu nowej dep) - ten target
# wymusza wykluczenie pakietow opublikowanych w ostatnich 3 dniach.
# Chroni przed atakami typu LiteLLM (zlosliwa wersja przez ~2.5h zanim
# PyPI quarantine zadziala). Praktyka #2 z pypi-security-best-practices.
#
# Wyjatki (--exclude-newer-package <pkg>=<future date>): pakiety in-house
# *-iplweb publikowane przez ten sam team co BPP. Cooldown na nie nie ma
# sensu (jakby konto bylo skompromitowane, atakujacy uderzylby tez tutaj),
# a swieze releasy sa czesto load-bearing.
#
# Override cutoff przez env var: make uv-lock-cooldown CUTOFF=2026-04-20T00:00:00Z
uv-lock-cooldown: ## uv lock z 3-dniowym cooldownem (defense-in-depth)
	@CUTOFF=$${CUTOFF:-$$(date -u -v-3d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '3 days ago' +%Y-%m-%dT%H:%M:%SZ)}; \
	FAR=2099-01-01T00:00:00Z; \
	echo "Excluding packages newer than $$CUTOFF (in-house *-iplweb exempt)"; \
	uv lock --exclude-newer "$$CUTOFF" \
		--exclude-newer-package "django-denorm-iplweb=$$FAR" \
		--exclude-newer-package "django-password-policies-iplweb=$$FAR" \
		--exclude-newer-package "MOAI-iplweb=$$FAR" \
		--exclude-newer-package "django_redis_iplweb=$$FAR" \
		--exclude-newer-package "pymed-iplweb=$$FAR" \
		--exclude-newer-package "django-dbtemplates-iplweb=$$FAR"

##@ GitHub Actions

gh-run-watch: ## `gh run watch` — obserwuj najnowszy run CI
	gh run watch

gh-run-watch-docker-images: ## Obserwuj najnowszy run workflow "Docker - oficjalne obrazy"
	gh run watch $$(gh run list --workflow="Docker - oficjalne obrazy" --limit=1 --json databaseId --jq '.[0].databaseId')

gh-run-watch-docker-images-alt: ## Alternatywna wersja gh-run-watch-docker-images (pipe)
	gh run list --workflow="Docker - oficjalne obrazy" --limit=1 --json databaseId --jq '.[0].databaseId' | xargs gh run watch

docker-images-on-ci: ## Wyślij build "Docker - oficjalne obrazy" na CI i obserwuj go
	@BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
	UPSTREAM=$$(git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>/dev/null || true); \
	if [ -z "$$UPSTREAM" ]; then \
		echo "BŁĄD: Gałąź $$BRANCH nie ma upstreamu. Wypchnij ją najpierw na remote."; \
		exit 1; \
	fi; \
	if [ -n "$$(git status --porcelain)" ]; then \
		echo "BŁĄD: Working tree zawiera niezcommitowane zmiany. Zcommituj lub stashuj je przed wysłaniem buildu na CI."; \
		exit 1; \
	fi; \
	if [ "$$(git rev-parse HEAD)" != "$$(git rev-parse "$$UPSTREAM")" ]; then \
		echo "BŁĄD: Lokalna gałąź $$BRANCH nie jest zsynchronizowana z $$UPSTREAM."; \
		echo "      Wypchnij zmiany przed wysłaniem buildu na CI."; \
		exit 1; \
	fi; \
	echo "Wysyłam build Docker - oficjalne obrazy na CI dla gałęzi: $$BRANCH"; \
	gh workflow run build-docker-images.yml --ref "$$BRANCH"; \
	echo "Czekam na pojawienie się runu..."; \
	sleep 3; \
	RUN_ID=$$(gh run list --workflow="Docker - oficjalne obrazy" --branch="$$BRANCH" --limit=1 --json databaseId --jq '.[0].databaseId'); \
	if [ -z "$$RUN_ID" ]; then \
		echo "BŁĄD: Nie udało się znaleźć nowego runu workflow."; \
		exit 1; \
	fi; \
	echo "Obserwuję run ID: $$RUN_ID"; \
	gh run watch "$$RUN_ID"

##@ Wersjonowanie i release

sleep-3: ## `sleep 3` (helper używany w pipeline release)
	sleep 3

##@ Django — zarządzanie

generate-500-page: ## Wygeneruj statyczną stronę 500.html z szablonu 50x.html
	uv run python src/manage.py generate_500_page

##@ Wersjonowanie i release

scan-deps: ## Skan zaleznosci (SBOM + OSV/Grype/Trivy) - blokuje przy HIGH/CRITICAL
	./bin/scan-deps.sh

new-release: scan-deps uv-lock upgrade-version sleep-3 gh-run-watch-docker-images ## Pełny pipeline release'u (skan deps + uv-lock + bumpver + watch CI)

check-clean-tree: ## Zawołaj błąd, jeśli working tree brudne (pre-release guard)
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working tree is dirty. Commit or stash changes before releasing."; \
		exit 1; \
	fi

release: check-clean-tree full-tests new-release ## Pełny release (tree clean + full-tests + new-release)

.PHONY: release-candidate release-promote
release-candidate: ## Faza 1: utnij kandydata (RC → :staging) i obserwuj run [SKIP_TESTS=1 SKIP_SCAN=1 WEB=1]
	@FLAGS=""; \
	if [ -n "$$SKIP_TESTS" ]; then FLAGS="$$FLAGS -f skip_tests=true"; fi; \
	if [ -n "$$SKIP_SCAN" ]; then FLAGS="$$FLAGS -f skip_scan=true"; fi; \
	echo "Odpalam release-candidate.yml (--ref dev)$$FLAGS ..."; \
	gh workflow run release-candidate.yml --ref dev $$FLAGS; \
	echo "Czekam na pojawienie się runu..."; \
	sleep 3; \
	RUN_ID=$$(gh run list --workflow=release-candidate.yml --limit=1 --json databaseId --jq '.[0].databaseId'); \
	if [ -z "$$RUN_ID" ]; then \
		echo "BŁĄD: Nie udało się znaleźć nowego runu workflow."; \
		exit 1; \
	fi; \
	echo "Obserwuję run ID: $$RUN_ID"; \
	if [ -n "$$WEB" ]; then gh run view "$$RUN_ID" --web; fi; \
	gh run watch "$$RUN_ID"

release-promote: ## Faza 2: promuj kandydata do produkcji (:latest, bez rebuildu) i obserwuj run [VERSION=vXXX WEB=1]
	@FLAGS=""; \
	if [ -n "$$VERSION" ]; then FLAGS="-f version=$$VERSION"; fi; \
	echo "Odpalam promote.yml$$FLAGS ..."; \
	gh workflow run promote.yml $$FLAGS; \
	echo "Czekam na pojawienie się runu..."; \
	sleep 3; \
	RUN_ID=$$(gh run list --workflow=promote.yml --limit=1 --json databaseId --jq '.[0].databaseId'); \
	if [ -z "$$RUN_ID" ]; then \
		echo "BŁĄD: Nie udało się znaleźć nowego runu workflow."; \
		exit 1; \
	fi; \
	echo "Obserwuję run ID: $$RUN_ID"; \
	if [ -n "$$WEB" ]; then gh run view "$$RUN_ID" --web; fi; \
	gh run watch "$$RUN_ID"

set-version-from-vcs: ## Ustaw wersję bumpver na podstawie git describe
	$(eval CUR_VERSION_VCS=$(shell git describe | sed s/\-/\./ | sed s/\-/\+/))
	bumpver update --no-commit --set-version=$(CUR_VERSION_VCS)

# Version management targets for development workflow
bump-dev: ## Podbij wersję do kolejnego -devN (tag=dev)
	@echo "Bumping to next development version..."
	uv run bumpver update --tag dev --tag-num
	@echo "New development version created. Build with: docker compose build"

bump-release: ## Zdejmij -dev z wersji (tag=final)
	@echo "Creating release version (removing -dev tag)..."
	uv run bumpver update --tag final
	@echo "Release version created. You may want to run: make bump-dev"

bump-and-start-dev: ## Release bieżącej + od razu nowy cykl dev
	@echo "Releasing current version and starting next development cycle..."
	uv run bumpver update --tag final
	@echo "Released. Now bumping to next dev version..."
	uv run bumpver update --tag dev --tag-num
	@echo "Ready for development. Build with: docker compose build"

.PHONY: check-git-clean
check-git-clean: ## Wyrzuć błąd jeśli `git diff` pokazuje zmiany
	git diff --quiet

test-package-from-vcs: check-git-clean uv-sync set-version-from-vcs ## Przetestuj uv build z wersją z VCS (reset --hard po!)
	uv build
	ls -lash dist
	git reset --hard

##@ Różne

loc: clean ## Pokaż statystyki liczby linii (pygount)
	pygount -N ... -F "...,staticroot,migrations,fixtures" src --format=summary


DOCKER_VERSION=202607.1396

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

##@ Docker build (buildx bake)

# Main build target - parallel builds using docker buildx bake
# This builds all images in parallel where possible:
# - base: builds first
# - appserver, workerserver, beatserver, authserver, denorm-queue: wait for base
# Obraz dbservera (iplweb/bpp_dbserver) jest budowany w osobnym repo:
# https://github.com/iplweb/bpp-dbserver
build: ## Równoległy build wszystkich obrazów (buildx bake)
	docker buildx bake $(BAKE_ARGS)

# Force rebuild all images (ignores cache)
build-force: ## Pełny rebuild ignorujący cache
	docker buildx bake $(BAKE_ARGS) --no-cache

# Build only the base image
build-base: ## Zbuduj tylko obraz `base`
	docker buildx bake $(BAKE_ARGS) base

# Build app services only (requires base image to exist)
build-app-services: ## Zbuduj tylko app-services (wymaga istniejącego `base`)
	docker buildx bake $(BAKE_ARGS) app-services

# Individual build targets (for debugging or specific rebuilds)
build-appserver-base: ## Alias do build-base (buduje base dla appservera)
	docker buildx bake $(BAKE_ARGS) base

build-appserver: ## Zbuduj tylko appserver
	docker buildx bake $(BAKE_ARGS) appserver

build-workerserver: ## Zbuduj tylko workerserver
	docker buildx bake $(BAKE_ARGS) workerserver

build-beatserver: ## Zbuduj tylko beatserver
	docker buildx bake $(BAKE_ARGS) beatserver

build-authserver: ## Zbuduj tylko authserver
	docker buildx bake $(BAKE_ARGS) authserver

build-denorm-queue: ## Zbuduj tylko denorm-queue
	docker buildx bake $(BAKE_ARGS) denorm-queue

# Alias for backward compatibility
build-servers: build ## Alias do `build` (kompatybilność wsteczna)

# =============================================================================
# Budowanie obrazów z brancha na Docker Build Cloud
# =============================================================================
#
# Użycie:
#   git push
#   make build-branch
#
# Obrazy trafiają na Docker Hub z tagiem = sanityzowana nazwa brancha.
# Tag "latest" NIE jest ustawiany (tylko buildy z mastera mają "latest").
#
# Na serwerze docelowym:
#   export DOCKER_VERSION=feature-nowe-zglos-publikacje
#   docker compose pull && docker compose up -d
#
# =============================================================================
# UWAGA: Celowo budujemy TYLKO dla platformy linux/amd64 (x86_64).
#
# Wszystkie nasze serwery produkcyjne działają na architekturze x86_64,
# więc nie ma potrzeby budowania obrazów ARM. Budowanie na dwie platformy
# trwa dłużej i zużywa więcej zasobów Docker Build Cloud.
#
# Jeśli w przyszłości pojawi się potrzeba budowania również na ARM
# (np. dla serwerów ARM lub lokalnego testowania na Apple Silicon),
# wystarczy zmienić BRANCH_BUILD_PLATFORM na linux/amd64,linux/arm64
# — wtedy Docker Build Cloud zbuduje obrazy na obie platformy
# automatycznie.
# =============================================================================
CLOUD_BUILDER = cloud-iplweb-bpp
BRANCH_BUILD_PLATFORM = linux/amd64

build-branch: ## Zbuduj i wypchnij obrazy z aktualnego brancha do Docker Hub (linux/amd64)
	$(eval BRANCH_TAG := $(shell git rev-parse --abbrev-ref HEAD \
	    | sed 's/[^a-zA-Z0-9._-]/-/g' \
	    | tr '[:upper:]' '[:lower:]'))
	@echo "========================================"
	@echo "Building branch: $(BRANCH_TAG)"
	@echo "Builder: $(CLOUD_BUILDER)"
	@echo "Platform: $(BRANCH_BUILD_PLATFORM)"
	@echo "========================================"
	DOCKER_VERSION=$(BRANCH_TAG) TAG_LATEST=false PUSH=true \
	    docker buildx bake \
	    --builder=$(CLOUD_BUILDER) \
	    --file docker-bake.hcl \
	    --set '*.platform=$(BRANCH_BUILD_PLATFORM)' \
	    --allow=fs.read=/tmp \
	    --allow=fs.write=/tmp

##@ Docker buildx cache

buildx-cache-stats: ## Pokaż `docker buildx du` (rozmiar cache)
	docker buildx du

buildx-cache-prune: ## Wyczyść cache buildx (ostrożnie)
	docker buildx prune

buildx-cache-prune-aggressive: ## Wyczyść cache buildx, zostaw tylko 5GB
	docker buildx prune --keep-storage 5GB

buildx-cache-prune-registry: ## Instrukcja usuwania cache z Docker Hub (manual)
	@echo "Note: Registry caches on Docker Hub must be pruned manually."
	@echo "Use 'docker rmi iplweb/bpp_*:cache' to remove local copies of registry caches."

buildx-cache-export: ## Wyeksportuj build cache do /tmp/docker-buildx-cache-backup
	@echo "Exporting build cache to local directory..."
	mkdir -p /tmp/docker-buildx-cache-backup
	docker buildx build --cache-to=type=local,dest=/tmp/docker-buildx-cache-backup,mode=max --load --target=scratch -f- . <<< "FROM scratch"

buildx-cache-import: ## Zaimportuj build cache z /tmp/docker-buildx-cache-backup
	@echo "Importing build cache from local directory..."
	if [ -d /tmp/docker-buildx-cache-backup ]; then \
		echo "Cache backup found at /tmp/docker-buildx-cache-backup"; \
	else \
		echo "No cache backup found. Run 'make buildx-cache-export' first."; \
		exit 1; \
	fi

buildx-cache-list: ## Wypisz znane nazwy cache'y rejestru na Docker Hub
	@echo "Registry caches on Docker Hub:"
	@echo "  - iplweb/bpp_base:cache"
	@echo "  - iplweb/bpp_appserver:cache"
	@echo "  - iplweb/bpp_workerserver:cache"
	@echo "  - iplweb/bpp_beatserver:cache"
	@echo "  - iplweb/bpp_denorm_queue:cache"

##@ Docker compose

compose-restart: ## Restart stacka docker-compose (stop + rm + up --force-recreate)
	docker compose stop
	docker compose rm -f
	docker compose up --force-recreate

compose-dbshell: ## Bash w kontenerze bazy danych (docker compose exec db bash)
	docker compose exec db /bin/bash


##@ Celery

celery-worker-run: ## Uruchom celery worker (pool=threads, concurrency=0)
	uv run celery -A django_bpp.celery_tasks worker --pool=threads --concurrency=0

celery-purge: ## Wyczyść kolejki denorm i celery (purge -f)
	DJANGO_SETTINGS_MODULE=django_bpp.settings.local uv run celery -A django_bpp.celery_tasks purge -Q denorm,celery -f

celery-worker-normal: ## Worker solo dla normalnych kolejek
	uv run celery --app=django_bpp.celery_tasks worker --concurrency=1 --loglevel=INFO  -P solo --without-gossip --without-mingle --without-heartbeat

celery-worker-denorm: ## Worker solo tylko dla kolejki denorm
	uv run celery --app=django_bpp.celery_tasks worker -Q denorm --concurrency=1 --loglevel=INFO  -P solo --without-gossip --without-mingle --without-heartbeat

##@ Django — zarządzanie

denorm-queue: ## Uruchom `manage.py denorm_queue`
	uv run python src/manage.py denorm_queue

migrate: ## Uruchom `manage.py migrate`
	uv run python src/manage.py migrate

cache-delete: ## `manage.py clear_cache` — wyczyść cache Django
	python src/manage.py clear_cache

##@ Celery

docker-celery-inspect: ## Wykonaj celery inspect (active, active_queues, stats) na workerserver
	docker compose exec workerserver uv run celery -A django_bpp.celery_tasks inspect active
	docker compose exec workerserver uv run celery -A django_bpp.celery_tasks inspect active_queues
	docker compose exec workerserver uv run celery -A django_bpp.celery_tasks inspect stats | grep max-concurrency

##@ Docker compose

refresh: build ## Rebuild + restart całego stacka compose + prune
	docker system prune -f
	docker compose down
	docker compose up -d
	docker system prune -f

##@ Django — zarządzanie

remove-denorms: ## Opróżnij tabelę denorm_dirtyinstance
	echo "DELETE FROM denorm_dirtyinstance;" | uv run python src/manage.py dbshell

##@ Czyszczenie

clean-docker-cache: ## Wyczyść cały cache Docker buildera i volumy (agresywne!)
	docker builder prune
	docker builder prune --all
	docker system prune -a --volumes
	rm -rf /tmp/.buildx-cache*

##@ Django — zarządzanie

invalidate: ## Unieważnij cały cache template fragments (`manage.py invalidate all`)
	uv run src/manage.py invalidate all

##@ Docker compose

prune-orphan-volumes: ## docker volume prune -f
	docker volume prune -f

open-docker-volume: prune-orphan-volumes ## Wybierz volume przez fzf i wejdź do niego shellem
	@VOLUME=$$(docker volume ls --format '{{.Name}}' | fzf --prompt="Select volume: ") && \
	docker run --rm -it -v "$$VOLUME":/volume -w /volume alpine:latest /bin/sh -c "ls -las; exec /bin/sh"

open-all-docker-volumes:  prune-orphan-volumes ## Zamontuj wszystkie volumy kontekstu w alpinie
	@MOUNTS=$$(docker volume ls --format '{{.Name}}' | grep "^$(CONTEXT_NAME)_" | while read vol; do \
		name=$${vol#$(CONTEXT_NAME)_}; \
		echo "-v $$vol:/volumes/$$name"; \
	done | tr '\n' ' ') && \
	docker run --rm -it $$MOUNTS -w /volumes alpine:latest /bin/sh -c "ls -las; exec /bin/sh"
