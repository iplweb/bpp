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
	find . -name \*\\.log -print0 | xargs -0 rm -f
	find . -name \*\\.log -print0 | xargs -0 rm -f
	find . -name \#\* -print0 | xargs -0 rm -f
	rm -rf build dist/*django_bpp*whl dist/*bpp_iplweb*whl *.log dist
	rm -rf src/django_bpp/staticroot/CACHE
	rm -rf .tox
	rm -rf *xlsx pbn_json_data/

distclean: clean
	rm -rf src/django_bpp/staticroot
	rm -rf *backup
	rm -rf node_modules src/node_modules src/django_bpp/staticroot
	rm -rf .vagrant splintershots src/components/bower_components src/media
	rm -rf dist

grunt:
	grunt build

yarn:
	yarn install --no-progress --emoji false -s

assets: yarn grunt
	${PYTHON} src/manage.py collectstatic --noinput -v0 --traceback
	${PYTHON} src/manage.py compress --force  -v0 --traceback

clean-node-dir:
	rm -rf node_modules

pre-wheel: distclean assets

bdist_wheel: pre-wheel
	${PYTHON} setup.py -q bdist_wheel

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

# cel: Jenkins
# Wywołaj "make jenkins" pod Jenkinsem, cel "Virtualenv Builder"
jenkins:
	pip install --upgrade pip --quiet
	pip install -r requirements.txt -r requirements_dev.txt --quiet
	make assets

	pytest --ds=django_bpp.settings.local -n6 --create-db --maxfail=20

	yarn
	make js-tests

pip-compile:
	pip-compile --output-file requirements.txt requirements.in
	pip-compile --output-file requirements_dev.txt requirements_dev.in

pip-sync:
	pip-sync requirements.txt requirements_dev.txt

pip: pip-compile pip-sync

tests:
	pytest -n 4 --splinter-headless

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
	python src/manage.py pbn_integrator --enable-all --start-from-stage=16

integration-start-from-match-single-thread:
	python src/manage.py pbn_integrator --enable-all --start-from-stage=16 --disable-multiprocessing
