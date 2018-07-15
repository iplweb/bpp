BRANCH=`git branch | sed -n '/\* /s///p'`

.PHONY: clean distclean tests release

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

grunt:
	grunt build

yarn:
	yarn

yarn-prod:
	yarn --prod

_assets:
	${PYTHON} src/manage.py collectstatic --noinput -v0 --traceback
	${PYTHON} src/manage.py compress --force  -v0 --traceback

assets: yarn grunt _assets


docker-assets: docker-grunt
	docker-compose run --rm python bash -c "cd /usr/src/app && pipenv --bare install --system && make _assets"

docker-grunt:
	docker-compose run --rm node bash -c "cd /usr/src/app && make yarn grunt"

# cel: assets
# Pobiera i składa do kupy JS/CSS/Foundation
assets: yarn _assets

assets-production: yarn-production _assets

requirements.txt:
	pipenv lock -r > requirements.txt

_bdist_wheel: requirements.txt
	${PYTHON} setup.py -q bdist_wheel

# cel: bdist_wheel
# Buduje pakiet WHL zawierający django_bpp i skompilowane, statyczne assets. 
# Wymaga:
# 1) zainstalowanych pakietów z requirements.txt i requirements_dev.txt przez pip
# 2) yarn, grunt-cli, npm, bower
bdist_wheel: clean assets _bdist_wheel

js-tests:
	grunt qunit

docker-js-tests:
	docker-compose run --rm node bash -c "cd /usr/src/app && make js-tests"

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
	VBoxManage clonevm `VBoxManage list vms|grep bpp_staging|cut -f 2 -d\  ` --name Demo\ BPP\ `python src/django_bpp/version.py` --register
	VBoxManage export Demo\ BPP\ `python src/django_bpp/version.py` -o bpp-`python src/django_bpp/version.py`.ova --options nomacs --options manifest --vsys 0 --product "Maszyna wirtualna BPP" --producturl http://iplweb.pl/kontakt/ --vendor IPLWeb --vendorurl http://iplweb.pl --version `python src/django_bpp/version.py` --eulafile LICENSE

# cel: demo-vm-cleanup
# Usuwa klon demo-maszyny wirutalnej
demo-vm-cleanup:
	VBoxManage unregistervm Demo\ BPP\ `python src/django_bpp/version.py` --delete

vagrantclean:
	vagrant destroy -f

vagrantup:
	vagrant up 

demo-vm: vagrantclean vagrantup staging demo-vm-ansible demo-vm-clone demo-vm-cleanup

cleanup-pycs:
	find . -name __pycache__ -type d -print0 | xargs -0 rm -rf
	find . -name \*~ -print0 | xargs -0 rm -f 
	find . -name \*pyc -print0 | xargs -0 rm -f 
	find . -name \*\\.log -print0 | xargs -0 rm -f 
	rm -rf build __pycache__ *.log

# cel: docker-up
# Podnosi wszystkie kontenery, które powinny działać w tle
docker-up:
	docker-compose up -d redis rabbitmq selenium nginx_http_push db

docker-python-tests: 
	docker-compose up -d test
	docker-compose exec test /bin/bash -c "cd /usr/src/app && make requirements.txt"
	docker-compose exec test /bin/bash -c "cd /usr/src/app && tox"

docker-tests: docker-assets docker-python-tests docker-js-tests

circle-env:
	echo COVERALLS_REPO_TOKEN="${COVERALLS_REPO_TOKEN}" >> docker/env.test.txt

# cel: production -DCUSTOMER=... or CUSTOMER=... make production
production: 
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/${CUSTOMER}/ansible/hosts.cfg" ansible/webserver.yml ${ANSIBLE_OPTIONS}

production-update: # "szybka" ścieżka aktualizacji
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/${CUSTOMER}/ansible/hosts.cfg" ansible/webserver.yml -t django-site ${ANSIBLE_OPTIONS}

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs: 
	sphinx-autobuild -p 8080 -D language=pl docs/ docs/_build
