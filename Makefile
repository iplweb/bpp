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

yarn-production:
	yarn install --no-progress --emoji false -s --prod

_assets:
	${PYTHON} src/manage.py collectstatic --noinput -v0 --traceback
	${PYTHON} src/manage.py compress --force  -v0 --traceback

assets: yarn grunt _assets

assets-production: yarn-production grunt _assets

requirements:
	pipenv lock -r > requirements.txt
	pipenv lock -dr > requirements_dev.txt

_bdist_wheel: 
	${PYTHON} setup.py -q bdist_wheel

_bdist_wheel_upload:
	${PYTHON} setup.py -q bdist_wheel upload

_prod_assets: distclean assets-production

bdist_wheel: _prod_assets requirements _bdist_wheel

bdist_wheel_upload: _prod_assets requirements _bdist_wheel_upload

js-tests:
	grunt qunit

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs: 
	sphinx-autobuild -p 8080 -D language=pl docs/ docs/_build
