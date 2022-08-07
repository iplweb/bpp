BRANCH=`git branch | sed -n '/\* /s///p'`

.PHONY: clean distclean tests release

PYTHON=python3

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


yarn:
	yarn install --no-progress --emoji false -s

assets: yarn
	grunt build
	poetry run src/manage.py collectstatic --noinput -v0 --traceback
	poetry run src/manage.py compress --force  -v0 --traceback

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

# compilemessages
	export PYTHONPATH=. && cd src && django-admin.py compilemessages

bdist_wheel: distclean production-assets
	poetry build
	ls -lash dist

upload:
	twine upload dist/*

js-tests:
	grunt qunit

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs:
	# Nie wrzucam instalacji sphinx-autobuild do requirements_dev.in
	# celowo i z premedytacją:
	pip install --upgrade sphinx-autobuild
	sphinx-autobuild --port 8080 -D language=pl docs/ docs/_build

tests:
	pytest -n 5 --splinter-headless --maxfail 50

remove-match-publikacji-dane:
	cd src/import_dbf && export CUSTOMER=foo && make disable-trigger
	python src/manage.py pbn_integrator --clear-match-publications
	cd src/import_dbf && export CUSTOMER=foo && make enable-trigger

remove-pbn-integracja-publikacji-dane:
	cd src/import_dbf && export CUSTOMER=foo && make disable-trigger
	python src/manage.py pbn_integrator --clear-publications
	cd src/import_dbf && export CUSTOMER=foo && make enable-trigger

remove-pbn-data:
	cd src/import_dbf && export CUSTOMER=foo && make disable-trigger
	python src/manage.py pbn_integrator --clear-all
	rm -rf pbn_json_data
	cd src/import_dbf && export CUSTOMER=foo && make enable-trigger

integration-start-from-match:
	python src/manage.py pbn_integrator --enable-all --start-from-stage=15

integration-start-from-download:
	python src/manage.py pbn_integrator --enable-all --start-from-stage=12

integration-start-from-match-single-thread:
	python src/manage.py pbn_integrator --enable-all --start-from-stage=15 --disable-multiprocessing

restart-pbn-from-download: remove-pbn-integracja-publikacji-dane integration-start-from-download

new-release:
	$(eval CUR_VERSION=$(shell ./bin/bpp-version.py))
	$(eval NEW_VERSION=$(shell bumpver test $(CUR_VERSION) 'vYYYY0M.BUILD[-TAGNUM]' |head -1|cut -d: -f2))
	git flow release start $(NEW_VERSION)
	bumpver update
	emacs HISTORY.rst
	git flow release finish "$(NEW_VERSION)" -p -m "Nowa wersja: $(NEW_VERSION)"

release: tests js-tests new-release bdist_wheel upload

set-version-from-vcs:
	$(eval CUR_VERSION_VCS=$(shell git describe | sed s/\-/\./ | sed s/\-/\+/))
	bumpver update --no-commit --set-version=$(CUR_VERSION_VCS)

.PHONY: check-git-clean
check-git-clean:
	git diff --quiet

poetry-sync:
	poetry install --no-root --remove-untracked

test-package-from-vcs: check-git-clean poetry-sync set-version-from-vcs bdist_wheel
	ls -lash dist
	git reset --hard
