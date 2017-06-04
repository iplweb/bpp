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
	rm -rf src/django_bpp/staticroot 

distclean: clean
	rm -rf dist/ dist_dev/ zarzadca*backup 
	rm -rf node_modules src/node_modules src/django_bpp/staticroot .eggs .cache .tox

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

# cel: build-assets
# Pobiera i składa do kupy JS/CSS/Foundation
build-assets: 
	./buildscripts/build-assets.sh

# cel: bdist_wheel
# Buduje pakiet WHL zawierający django_bpp i skompilowane, statyczne assets. 
# Wymaga:
# 1) zainstalowanych pakietów z requirements.txt i requirements_dev.txt przez pip
# 2) yarn, grunt-cli, npm, bower
bdist_wheel: install-wheels build-assets
	python setup.py bdist_wheel

# cel: tests-from-scratch
# Uruchamia testy całego site'u za pomocą docker-compose. Wymaga zbudowanych 
# pakietów WHL (cel: wheels) oraz statycznych assets w katalogu src/django_bpp/staticroot
# (cel: prepare-build-env)
tests: 
	tox

docker-up: 
	docker-compose up -d rabbitmq redis db selenium



#
# TODO: dockerize, analyze, remove below targets
#

release-no-tests: vcs wheels build-assets build staging
	@echo "Done"

release: vcs wheels tests-from-scratch build staging
	@echo "Done"

local-build:
	buildscripts/prepare-build-env.sh
	buildscripts/run-tests.sh

new-patch: clean
	bumpversion patch 
	git push
	git push --tags

rerun-release-after-tests-failure: vcs just-tests build staging
	@echo "Done"

download: 
	fab -H zarzadca@bpp.umlub.pl download_db

download-and-migrate: download migrate
	@echo "Done!"

_rebuild-from-downloaded:
	fab -H zarzadca@bpp.umlub.pl download_db:restore=True,recreate=True,download=False

rebuild-from-downloaded: _rebuild-from-downloaded migrate
	@echo "Done!"

migrate: 
	cd src && python manage.py migrate

rebuild: rebuild-from-downloaded migrate
	-say "Przebudowa bazy danych zakończona"
	@echo "Done"

production:
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/Biblioteka Glowna/ansible/hosts.cfg" ansible/webserver.yml

bppdemo:
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/IPL/ansible/hosts.cfg" ansible/webserver.yml

upload-db-to-staging:
	fab -i .vagrant/machines/staging/virtualbox/private_key -H ubuntu@bpp-staging.localnet upload_db:zarzadca@bpp.umlub.pl-bpp.backup,staging-bpp,staging-bpp


egeria-import:
	python src/manage.py egeria_import "/Volumes/Dane zaszyfrowane/Biblioteka Główna/wykaz-27.06.2016-mpasternak.xlsx"
	-say "Integracja autorów zakończona"

rebuild-reimport: rebuild egeria-import
	@echo "Done"

rebuilddb:
	-dropdb bpp
	-dropdb test_bpp
	createdb bpp
	python src/manage.py makemigrations
	python src/manage.py migrate
	-say "Przebudowa bazy danych zakończona"
	-noti -t "rebuilddb zakończono" -m "Proces przebudowania bazy danych zakończony"

pristine-staging:
	vagrant pristine -f staging

export:


vm-clone:
	-rm bpp-`python src/django_bpp/version.py`.ova
	vagrant halt staging
	VBoxManage clonevm `VBoxManage list vms|grep django-bpp_staging|cut -f 2 -d\  ` --name Demo\ BPP\ `python src/django_bpp/version.py` --register
	VBoxManage export Demo\ BPP\ `python src/django_bpp/version.py` -o bpp-`python src/django_bpp/version.py`.ova --options nomacs --options manifest --vsys 0 --product "Maszyna wirtualna BPP" --producturl http://iplweb.pl/kontakt/ --vendor IPLWeb --vendorurl http://iplweb.pl --version `python src/django_bpp/version.py` --eulafile LICENSE 

vm-cleanup: 
	# VBoxManage modifyvm Demo\ BPP\ `python src/django_bpp/version.py` -hda none
	VBoxManage unregistervm Demo\ BPP\ `python src/django_bpp/version.py` --delete

demo-vm: pristine-staging staging demo-vm-ansible vm-clone vm-cleanup
	@echo Done
