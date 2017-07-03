BRANCH=`git branch | sed -n '/\* /s///p'`

#
# UWAGA UWAGA UWAGA
# 
# Ten makefile buduje TYLKO lokalnie.
#
# Makefile ułatwiający rzeczy przez dockera nazywa się "Makefile.docker"
# 

.PHONY: clean distclean build-wheels install-wheels wheels tests release

PYTHON=python3.6
PIP=${PYTHON} -m pip
DISTDIR=./dist
DISTDIR_DEV=./dist_dev

clean:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rfv
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 
	find . -name \*\\.log -print0 | xargs -0 rm -fv 
	find . -name \*\\.log -print0 | xargs -0 rm -fv 
	find . -name \#\* -print0 | xargs -0 rm -fv
	rm -rf build dist/*django_bpp*whl __pycache__ *.log
	rm -rf .eggs .cache .tox

distclean: clean
	rm -rf src/django_bpp/staticroot 
	rm -rf dist/ dist_dev/ zarzadca*backup 
	rm -rf node_modules src/node_modules src/django_bpp/staticroot 
	rm -rf .vagrant splintershots src/components/bower_components src/media

dockerclean:
	docker-compose stop
	docker-compose rm -f

vagrantclean:
	vagrant destroy -f

# cel: wheels
# Buduje pakiety WHL. Nie buduje samego pakietu django-bpp
# Buduje pakiety WHL na bazie requirements.txt, zapisując je do katalogu 'dist',
# buduje pakiety WHL na bazie requirements_dev.txt, zapisując je do katalogu 'dist_dev'.
wheels:
	echo "Buduje wheels w ${DISTDIR}"

	mkdir -p ${DISTDIR}
	${PIP} wheel --wheel-dir=${DISTDIR} --find-links=${DISTDIR} -r requirements.txt 

	mkdir -p ${DISTDIR_DEV}
	${PIP} wheel --wheel-dir=${DISTDIR_DEV} --find-links=${DISTDIR} --find-links=${DISTDIR_DEV} -r requirements_dev.txt 

# cel: install-wheels
# Instaluje wszystkie requirements
install-wheels:
	${PIP} install -q --no-index --find-links=./dist --find-links=./dist_dev -r requirements_dev.txt

# cel: assets
# Pobiera i składa do kupy JS/CSS/Foundation
assets: 
	yarn install > /dev/null
	npm rebuild > /dev/null
	rm -rf src/django_bpp/staticroot
	${PYTHON} src/manage.py collectstatic --noinput -v0
	grunt build 
	${PYTHON} src/manage.py collectstatic --noinput -v0
	${PYTHON} src/manage.py compress --force  -v0
	echo -n "Static root size: "
	du -ch src/django_bpp/staticroot | grep total

# cel: bdist_wheel
# Buduje pakiet WHL zawierający django_bpp i skompilowane, statyczne assets. 
# Wymaga:
# 1) zainstalowanych pakietów z requirements.txt i requirements_dev.txt przez pip
# 2) yarn, grunt-cli, npm, bower
bdist_wheel: clean install-wheels assets 
	${PYTHON} setup.py bdist_wheel

# cel: tests
# Uruchamia testy całego site'u za pomocą docker-compose. Wymaga zbudowanych 
# pakietów WHL (cel: wheels) oraz statycznych assets w katalogu src/django_bpp/staticroot
# (cel: assets)
tests: # wymaga: wheels assets
	tox

# cel: tests-full
# Jak tests, ale całość
full-tests: wheels bdist_wheel tests


# cel: docker-up
# Startuje usługi dockera wymagane do lokalnego developmentu
# Zobacz też: setup-lo0
docker-up: 
	docker-compose up -d rabbitmq redis db selenium
	docker-compose ps


# cel: download
# Pobiera baze danych z hosta
download: 
	fab -H zarzadca@bpp.umlub.pl download_db

migrate: 
	cd src && ${PYTHON} manage.py migrate

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

# cel: setup-lo0
# Konfiguruje alias IP dla interfejsu lo0 aby kontener Dockera 'selenium'
# miał dostęp do live-serwera uruchamianego na komputerze hosta. Użyteczne
# pod Mac OS X
setup-lo0:
	sudo ifconfig lo0 alias 192.168.13.37

# cel: release
# PyPI release
release: clean assets
	${PYTHON} setup.py sdist upload
	${PYTHON} setup.py bdist_wheel upload

# cel: staging
# Konfiguruje system django-bpp za pomocą Ansible na komputerze 'staging' (vagrant)
staging: wheels bdist_wheel
	vagrant up staging
	ansible-playbook ansible/webserver.yml --private-key=.vagrant/machines/staging/virtualbox/private_key

demo-vm-ansible: 
	ansible-playbook ansible/demo-vm.yml --private-key=.vagrant/machines/staging/virtualbox/private_key

# cel: demo-vm-clone
# Tworzy klon Vagrantowego boxa "staging" celem stworzenia pliku OVA
# z demo-wersją maszyny wirtualnej.
demo-vm-clone:
	-rm bpp-`python src/django_bpp/version.py`.ova
	vagrant halt staging
	VBoxManage clonevm `VBoxManage list vms|grep django-bpp_staging|cut -f 2 -d\  ` --name Demo\ BPP\ `python src/django_bpp/version.py` --register
	VBoxManage export Demo\ BPP\ `python src/django_bpp/version.py` -o bpp-`python src/django_bpp/version.py`.ova --options nomacs --options manifest --vsys 0 --product "Maszyna wirtualna BPP" --producturl http://iplweb.pl/kontakt/ --vendor IPLWeb --vendorurl http://iplweb.pl --version `python src/django_bpp/version.py` --eulafile LICENSE

# cel: demo-vm-cleanup
# Usuwa klon demo-maszyny wirutalnej
demo-vm-cleanup:
	VBoxManage unregistervm Demo\ BPP\ `python src/django_bpp/version.py` --delete

demo-vm: vagrantclean staging demo-vm-ansible demo-vm-clone demo-vm-cleanup

travis: distclean dockerclean
	make -f Makefile.docker travis
