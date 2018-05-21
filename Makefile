BRANCH=`git branch | sed -n '/\* /s///p'`

.PHONY: clean distclean build-wheels install-wheels wheels tests release

PYTHON=python3.6
PIP=${PYTHON} -m pip
DISTDIR=./dist
DISTDIR_DEV=./dist_dev

clean-pycache:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rf
	find . -name \*pyc -print0 | xargs -0 rm -f
	rm -rf .eggs .cache	

clean: clean-pycache
	find . -name \*~ -print0 | xargs -0 rm -f 
	find . -name \*\\.log -print0 | xargs -0 rm -f 
	find . -name \*\\.log -print0 | xargs -0 rm -f 
	find . -name \#\* -print0 | xargs -0 rm -f
	rm -rf build dist/*django_bpp*whl *.log
	rm -rf .tox

distclean: clean
	rm -rf src/django_bpp/staticroot 
	rm -rf *backup 
	rm -rf node_modules src/node_modules src/django_bpp/staticroot 
	rm -rf .vagrant splintershots src/components/bower_components src/media

# cel: wheels
# Buduje pakiety WHL. Nie buduje samego pakietu django-bpp
# Buduje pakiety WHL na bazie requirements.txt, zapisując je do katalogu 'dist',
# buduje pakiety WHL na bazie requirements_dev.txt, zapisując je do katalogu 'dist_dev'.
wheels:
	echo "Buduje wheels w ${DISTDIR}"

	mkdir -p ${DISTDIR}
	${PIP}  wheel --wheel-dir=${DISTDIR} --find-links=${DISTDIR} -r requirements_src.txt  | cat

	mkdir -p ${DISTDIR}
	${PIP} wheel --wheel-dir=${DISTDIR} --find-links=${DISTDIR} -r requirements.txt | cat

	mkdir -p ${DISTDIR_DEV}
	${PIP} wheel --wheel-dir=${DISTDIR_DEV} --find-links=${DISTDIR} --find-links=${DISTDIR_DEV} -r requirements_dev.txt | cat

# cel: install-production-wheels
# Instaluje wszystkie requirements
install-production-wheels:
	${PIP} install -q --no-index --only-binary=whl --find-links=./dist -r requirements.txt

install-dev-wheels:
	${PIP} install -q --no-index --only-binary=whl --find-links=./dist_dev -r requirements_dev.txt

# cel: install-wheels
# Instaluje wszystkie requirements
install-wheels: install-production-wheels install-dev-wheels

install-wheels-from-devserver:
	${PIP} install --extra-index-url http://dev.iplweb.pl:8080/ --trusted-host dev.iplweb.pl -r requirements_dev.txt | cat

install-wheels-from-localdir:
	${PIP} install -f file://`pwd`/dist/ -f file://`pwd`/dist_dev/ -r requirements_dev.txt | cat

grunt:
	grunt build

yarn:
	yarn

yarn-production:
	yarn --prod

_real_assets: 
	${PYTHON} src/manage.py collectstatic --noinput -v0 --traceback
	${PYTHON} src/manage.py compress --force  -v0 --traceback

_assets: install-wheels-from-devserver _real_assets

_assets-localdir: install-wheels-from-localdir _real_assets

assets: yarn grunt _assets

_docker-assets:
	docker-compose run --rm python bash -c "cd /usr/src/app && make _assets"

_docker-assets-localdir:
	docker-compose run --rm python bash -c "cd /usr/src/app && make _assets-localdir"

docker-assets: docker-wheels docker-yarn docker-grunt _docker-assets-localdir

docker-grunt:
	docker-compose run --rm node bash -c "cd /usr/src/app && make grunt"

docker-yarn:
	docker-compose run --rm node bash -c "cd /usr/src/app && make yarn"

docker-yarn-prod:
	docker-compose run --rm node bash -c "cd /usr/src/app && make yarn-prod"

# cel: assets
# Pobiera i składa do kupy JS/CSS/Foundation
assets: yarn _assets

assets-production: yarn-production _assets

_bdist_wheel:
	${PYTHON} setup.py -q bdist_wheel

# cel: bdist_wheel
# Buduje pakiet WHL zawierający django_bpp i skompilowane, statyczne assets. 
# Wymaga:
# 1) zainstalowanych pakietów z requirements.txt i requirements_dev.txt przez pip
# 2) yarn, grunt-cli, npm, bower
bdist_wheel: clean assets _bdist_wheel rsync-dev


# cel: bdist_wheel-production
# Jak bdist_wheel, ale pakuje tylko produkcyjne JS prezz yarn
bdist_wheel-production: clean install-wheels assets-production _bdist_wheel

js-tests:
	ls -las src/django_bpp/staticroot
	grunt qunit -v

docker-js-tests:
	docker-compose run --rm node bash -c "cd /usr/src/app && make js-tests"

# cel: tests-full
# Jak tests, ale całość
full-tests: wheels install-wheels assets tests bdist_wheel-production
	coveralls

# cel: release
# PyPI release
release: bdist_wheel
	${PYTHON} setup.py -q sdist upload
	${PYTHON} setup.py -q bdist_wheel upload

# cel: staging
# Konfiguruje system django-bpp za pomocą Ansible na komputerze 'staging' (vagrant)
staging: # wymaga: wheels bdist_wheel
	vagrant up
	ansible-playbook ansible/webserver.yml --private-key=.vagrant/machines/staging/virtualbox/private_key

staging-update: # "szybka" ścieżka aktualizacji
	ansible-playbook ansible/webserver.yml -t django-site --private-key=.vagrant/machines/staging/virtualbox/private_key

pristine-staging:
	vagrant pristine -f staging
	echo -n "Sleeping for 10 secs..."
	sleep 10
	echo " done!" 

rebuild-staging: bdist_wheel pristine-staging staging


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

demo-vm: vagrantclean vagrantup staging demo-vm-ansible demo-vm-clone demo-vm-cleanup

cleanup-pycs:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rf
	find . -name \*~ -print0 | xargs -0 rm -f 
	find . -name \*pyc -print0 | xargs -0 rm -f 
	find . -name \*\\.log -print0 | xargs -0 rm -f 
	rm -rf build __pycache__ *.log

# cel: build-test-container
# Buduje testowy kontener
build-test-container: cleanup-pycs
	docker-compose stop test
	docker-compose rm test
	docker-compose build test > /dev/null

# cel: docker-up
# Podnosi wszystkie kontenery, które powinny działać w tle
docker-up:
	docker-compose up -d redis rabbitmq selenium nginx_http_push db

docker-python-tests:
	docker-compose up -d test
	docker-compose exec test /bin/bash -c "cd /usr/src/app && pip install -q tox && tox"

docker-tests: docker-assets docker-python-tests docker-js-tests

_docker-wheels:
	docker-compose run --rm python bash -c "cd /usr/src/app && make wheels"

rsync-dev:
	rsync dist/* dist_dev/* pypi@dev.iplweb.pl:~/packages

docker-wheels: _docker-wheels rsync-dev

circle-env:
	echo COVERALLS_REPO_TOKEN="${COVERALLS_REPO_TOKEN}" >> docker/env.test.txt

# cel: travis
# Uruchamia wszystkie testy - dla TravisCI
travisci: travis-env docker-up docker-tests
	@echo "Done"

rebuild-test:
	docker-compose stop test
	docker-compose rm -f test
	docker-compose build test

_docker-production-deps:
	docker-compose run --rm test /bin/bash -c "cd /usr/src/app && make install-production-wheels _bdist_wheel"

docker-production-deps: docker-assets clean _docker-production-deps


# cel: docker-build
# Tworzy zależności dla produkcyjnej wersji oprogramowania
# (czyli: buduje wheels i bdist_wheel pod dockerem, na docelowej
# dystrybucji Linuxa, następnie wpycha je do naszego "prywatnego" PyPI)
docker-build: docker-production-deps rsync-dev

# cel: production -DCUSTOMER=... or CUSTOMER=... make production
production: 
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/${CUSTOMER}/ansible/hosts.cfg" ansible/webserver.yml ${ANSIBLE_OPTIONS}

production-update: # "szybka" ścieżka aktualizacji
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/${CUSTOMER}/ansible/hosts.cfg" ansible/webserver.yml -t django-site ${ANSIBLE_OPTIONS}

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs: 
	sphinx-autobuild -p 8080 -D language=pl docs/ docs/_build

_circleci_pull:
	docker-compose pull db nginx_http_push node test python 

# cel: cirlceci
# Uruchom polecenia w kolejności takiej, jak w CircleCI, ale bez Coverage
# Przydatne gdy chcemy lokalnie uruchomić testy, przed pchnięciem kodu na GitHub
circleci: _circleci_pull docker-up docker-yarn docker-grunt _docker-assets docker-python-tests docker-js-tests
