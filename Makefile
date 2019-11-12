BRANCH=`git branch | sed -n '/\* /s///p'`

.PHONY: clean distclean tests release

PYTHON=python3.6

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
	find . -name \*~ -print0 | xargs -0 rm -f 
	find . -name \*\\.log -print0 | xargs -0 rm -f 
	find . -name \*\\.log -print0 | xargs -0 rm -f 
	find . -name \#\* -print0 | xargs -0 rm -f
	rm -rf build dist/*django_bpp*whl dist/*bpp_iplweb*whl *.log
	rm -rf src/django_bpp/staticroot/CACHE
	rm -rf .tox

distclean: clean
	rm -rf src/django_bpp/staticroot 
	rm -rf *backup 
	rm -rf node_modules src/node_modules src/django_bpp/staticroot 
	rm -rf .vagrant splintershots src/components/bower_components src/media

grunt:
	grunt build

yarn:
	yarn install --no-progress --emoji false -s

assets: yarn grunt
	${PYTHON} src/manage.py collectstatic --noinput -v0 --traceback
	${PYTHON} src/manage.py compress --force  -v0 --traceback

requirements:
	pipenv lock -r > requirements.txt
	pipenv lock -dr > requirements_dev.txt

clean-node-dir:
	rm -rf node_modules

pre-wheel: distclean assets requirements

bdist_wheel: pre-wheel
	${PYTHON} setup.py -q bdist_wheel

bdist_wheel_upload: pre-wheel
	${PYTHON} setup.py -q bdist_wheel upload

js-tests:
	grunt qunit

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs: 
	sphinx-autobuild -p 8080 -D language=pl docs/ docs/_build

# cel: Jenkins
# Wywołaj "make jenkins" pod Jenkinsem, cel "Virtualenv Builder"
jenkins:
	pip install pipenv
	pipenv install -d
	make assets

	pytest --ds=django_bpp.settings.local -n6 --splinter-webdriver=firefox --nginx-host=localhost --liveserver=localhost --create-db --maxfail=20

	yarn
	make js-tests
