BRANCH=`git branch | sed -n '/\* /s///p'`

#
# UWAGA UWAGA UWAGA
# 
# Ten makefile buduje TYLKO lokalnie.
#
# Makefile ułatwiający rzeczy przez dockera nazywa się "Makefile.dev"
# 

.PHONY: clean distclean build-wheels install-wheels wheels tests

clean:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rfv
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 
	find . -name \*\\.log -print0 | xargs -0 rm -fv 
	rm -rf build __pycache__ *.log

distclean: clean
	rm -rf src/django_bpp/staticroot 
	rm -rf dist/ dist_dev/ zarzadca*backup 
	rm -rf node_modules src/node_modules src/django_bpp/staticroot .eggs .cache .tox
	rm -rf .vagrant splintershots src/components/bower_components src/media
	docker-compose stop
	docker-compose rm -f

# cel: wheels
# Buduje pakiety WHL. Nie buduje samego pakietu django-bpp
# Buduje pakiety WHL na bazie requirements.txt, zapisując je do katalogu 'dist',
# buduje pakiety WHL na bazie requirements_dev.txt, zapisując je do katalogu 'dist_dev'.
wheels:
	./buildscripts/build-wheel.sh

# cel: install-wheels
# Instaluje wszystkie requirements
install-wheels:
	pip2 install -q --no-index --find-links=./dist --find-links=./dist_dev -r requirements_dev.txt

# cel: assets
# Pobiera i składa do kupy JS/CSS/Foundation
assets: 
	./buildscripts/build-assets.sh

# cel: bdist_wheel
# Buduje pakiet WHL zawierający django_bpp i skompilowane, statyczne assets. 
# Wymaga:
# 1) zainstalowanych pakietów z requirements.txt i requirements_dev.txt przez pip
# 2) yarn, grunt-cli, npm, bower
bdist_wheel: install-wheels assets clean
	python setup.py bdist_wheel

# cel: tests-from-scratch
# Uruchamia testy całego site'u za pomocą docker-compose. Wymaga zbudowanych 
# pakietów WHL (cel: wheels) oraz statycznych assets w katalogu src/django_bpp/staticroot
# (cel: prepare-build-env)
tests: 
	tox

docker-up: 
	docker-compose up -d rabbitmq redis db selenium
	docker-compose ps


# cel: download
# Pobiera baze danych z hosta
download: 
	fab -H zarzadca@bpp.umlub.pl download_db

migrate: 
	cd src && python manage.py migrate

download-and-migrate: download migrate
	@echo "Done!"

_rebuild-from-downloaded:
	fab -H zarzadca@bpp.umlub.pl download_db:restore=True,recreate=True,download=False

# cel: rebuild-from-downloaded
# Od-budowuje baze danych 
rebuild-from-downloaded: _rebuild-from-downloaded migrate
	@echo "Done!"

# cel: upload-db-to-staging
# Wrzuca pobraną bazę danych na staging-server
upload-db-to-staging:
	fab -i .vagrant/machines/staging/virtualbox/private_key -H ubuntu@bpp-staging.localnet upload_db:zarzadca@bpp.umlub.pl-bpp.backup,staging-bpp,staging-bpp
