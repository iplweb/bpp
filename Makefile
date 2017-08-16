BRANCH=`git branch | sed -n '/\* /s///p'`

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
	rm -rf *backup 
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
	${PIP} wheel --wheel-dir=${DISTDIR} --find-links=${DISTDIR} -r requirements_src.txt 

	mkdir -p ${DISTDIR}
	${PIP} wheel --wheel-dir=${DISTDIR} --find-links=${DISTDIR} -r requirements.txt 

	mkdir -p ${DISTDIR_DEV}
	${PIP} wheel --wheel-dir=${DISTDIR_DEV} --find-links=${DISTDIR} --find-links=${DISTDIR_DEV} -r requirements_dev.txt 

# cel: install-wheels
# Instaluje wszystkie requirements
install-wheels:
	${PIP} install --no-index --only-binary=whl --find-links=./dist --find-links=./dist_dev -r requirements_dev.txt

assets-for-django:
	rm -rf src/django_bpp/staticroot
	${PYTHON} src/manage.py collectstatic --noinput -v0
	grunt build 
	${PYTHON} src/manage.py collectstatic --noinput -v0
	${PYTHON} src/manage.py compress --force  -v0

yarn: 
	yarn > /dev/null

yarn-production:
	yarn --prod > /dev/null

# cel: assets
# Pobiera i składa do kupy JS/CSS/Foundation
assets: yarn assets-for-django 

assets-production: yarn-production assets-for-django

_bdist_wheel:
	${PYTHON} setup.py bdist_wheel

# cel: bdist_wheel
# Buduje pakiet WHL zawierający django_bpp i skompilowane, statyczne assets. 
# Wymaga:
# 1) zainstalowanych pakietów z requirements.txt i requirements_dev.txt przez pip
# 2) yarn, grunt-cli, npm, bower
bdist_wheel: clean install-wheels assets _bdist_wheel


# cel: bdist_wheel-production
# Jak bdist_wheel, ale pakuje tylko produkcyjne JS prezz yarn
bdist_wheel-production: clean install-wheels assets-production _bdist_wheel

# cel: tests
# Uruchamia testy całego site'u za pomocą tox. Wymaga zbudowanych 
# pakietów WHL (cel: wheels), zainstalowanych pakietów wheels
# (cel: install-wheels) oraz statycznych assets w katalogu 
# src/django_bpp/staticroot (cel: assets)
tests:
	tox

# cel: tests-full
# Jak tests, ale całość
full-tests: wheels install-wheels assets tests bdist_wheel-production


# cel: docker-up
# Startuje usługi dockera wymagane do lokalnego developmentu
# Zobacz też: setup-lo0
docker-up: 
	docker-compose up -d rabbitmq redis db selenium
	docker-compose ps


# cel: setup-lo0
# Konfiguruje alias IP dla interfejsu lo0 aby kontener Dockera 'selenium'
# miał dostęp do live-serwera uruchamianego na komputerze hosta. Użyteczne
# pod Mac OS X
setup-lo0:
	sudo ifconfig lo0 alias 192.168.13.37

# cel: release
# PyPI release
release: bdist_wheel
	${PYTHON} setup.py sdist upload
	${PYTHON} setup.py bdist_wheel upload

# cel: staging
# Konfiguruje system django-bpp za pomocą Ansible na komputerze 'staging' (vagrant)
staging: # wymaga: wheels bdist_wheel
	ansible-playbook ansible/webserver.yml --private-key=.vagrant/machines/staging/virtualbox/private_key

pristine-staging:
	vagrant pristine -f staging
	echo -n "Sleeping for 10 secs..."
	sleep 10
	echo " done!" 

rebuild-staging: bdist_wheel pristine-staging staging upload-db-to-staging


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

cleanup-pycs:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rfv
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 
	find . -name \*\\.log -print0 | xargs -0 rm -fv 
	rm -rf build __pycache__ *.log

# cel: build-test-container
# Buduje testowy kontener
build-test-container: cleanup-pycs
	docker-compose stop test
	docker-compose rm test
	docker-compose build test

# cel: travis
# Uruchamia wszystkie testy - dla TravisCI
travis: distclean dockerclean build-test-container
	docker-compose run --rm test "make full-tests"

# cel: production-deps
# Tworzy zależności dla produkcyjnej wersji oprogramowania
# (czyli: buduje wheels i bdist_wheel pod dockerem, na docelowej
# dystrybucji Linuxa)
production-deps: 
	docker-compose run --rm test "make wheels bdist_wheel"

# cel: production -DCUSTOMER=... or CUSTOMER=... make production
production: 
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/${CUSTOMER}/ansible/hosts.cfg" ansible/webserver.yml ${ANSIBLE_OPTIONS}

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs: 
	sphinx-autobuild -p 8080 -D language=pl docs/ docs/_build