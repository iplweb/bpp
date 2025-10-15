BRANCH=`git branch | sed -n '/\* /s///p'`

.PHONY: clean distclean tests release tests-without-selenium tests-with-selenium docker destroy-test-databases

PYTHON=python3

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

tests-without-selenium:
	uv run pytest -n auto --splinter-headless -m "not selenium and not playwright" --maxfail 50

tests-without-selenium-with-microsoft-auth:
	uv run pytest -n auto --splinter-headless -m "not selenium and not playwright" --maxfail 50

tests-with-microsoft-auth: enable-microsoft-auth tests-without-selenium-with-microsoft-auth disable-microsoft-auth

tests-with-selenium:
	uv run pytest -n auto  --splinter-headless -m "selenium or playwright"

tests: tests-without-selenium tests-with-selenium js-tests

destroy-test-databases:
	-./bin/drop-test-databases.sh

full-tests: destroy-test-databases tests-with-microsoft-auth destroy-test-databases tests js-tests


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

new-release: uv-lock upgrade-version sleep-3 gh-run-watch-docker-images

release: full-tests new-release

set-version-from-vcs:
	$(eval CUR_VERSION_VCS=$(shell git describe | sed s/\-/\./ | sed s/\-/\+/))
	bumpver update --no-commit --set-version=$(CUR_VERSION_VCS)

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


DOCKER_VERSION="202510.1251"

DOCKER_BUILD=build --platform linux/amd64 --push


# Na lokalnej maszynie nie uzywaj --push + buduj tylko ARM
HOST="$(shell hostname)"
ifeq (${HOST},"swift-beast.local")
DOCKER_BUILD=build --platform linux/arm64
endif

build-dbserver: deploy/dbserver/Dockerfile deploy/dbserver/autotune.py deploy/dbserver/docker-entrypoint-autotune.sh
	docker buildx ${DOCKER_BUILD} -t iplweb/bpp_dbserver:${DOCKER_VERSION} -t iplweb/bpp_dbserver:latest -f deploy/dbserver/Dockerfile deploy/dbserver/

build-appserver-base:
	docker buildx ${DOCKER_BUILD} -t iplweb/bpp_base:${DOCKER_VERSION} -t iplweb/bpp_base:latest -f deploy/bpp_base/Dockerfile .

build-appserver: build-appserver-base
	docker buildx ${DOCKER_BUILD} -t iplweb/bpp_appserver:${DOCKER_VERSION} -t iplweb/bpp_appserver:latest -f deploy/appserver/Dockerfile .

build-workerserver: build-appserver-base
	docker buildx ${DOCKER_BUILD} -t iplweb/bpp_workerserver:${DOCKER_VERSION} -t iplweb/bpp_workerserver:latest -f deploy/workerserver/Dockerfile .

build-webserver: deploy/webserver/Dockerfile deploy/webserver/default.conf.template deploy/webserver/maintenance.html deploy/webserver/key.pem deploy/webserver/cert.pem
	docker buildx ${DOCKER_BUILD} -t iplweb/bpp_webserver:${DOCKER_VERSION} -t iplweb/bpp_webserver:latest -f deploy/webserver/Dockerfile deploy/webserver/

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
	docker buildx ${DOCKER_BUILD} -t iplweb/bpp_beatserver:${DOCKER_VERSION} -t iplweb/bpp_beatserver:latest -f deploy/beatserver/Dockerfile deploy/beatserver/

build-flower:
	docker buildx ${DOCKER_BUILD} -t iplweb/flower:${DOCKER_VERSION} -t iplweb/flower:latest -f deploy/flower/Dockerfile deploy/flower/

build-servers: build-appserver-base build-appserver build-workerserver build-beatserver build-flower

docker: build-dbserver build-webserver build-servers

compose-restart:
	docker compose stop
	docker compose rm -f
	docker compose up --force-recreate

compose-dbshell:
	docker compose exec db /bin/bash
