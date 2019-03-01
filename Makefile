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

# cel: staging
# Konfiguruje system django-bpp za pomocą Ansible na komputerze 'staging' (vagrant)
staging: staging-up staging-ansible

staging-up: 
	vagrant up

staging-ansible:
	ansible-playbook ansible/webserver.yml --private-key=.vagrant/machines/staging/virtualbox/private_key

staging-update: # "szybka" ścieżka aktualizacji
	ansible-playbook ansible/webserver.yml -t django-site --private-key=.vagrant/machines/staging/virtualbox/private_key

pristine-staging:
	vagrant pristine -f staging

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
	VBoxManage export Demo\ BPP\ `python src/django_bpp/version.py` -o bpp-`python src/django_bpp/version.py`-`date +%Y%m%d%H%M`.ova --options nomacs --options manifest --vsys 0 --product "Maszyna wirtualna BPP" --producturl http://iplweb.pl/kontakt/ --vendor IPLWeb --vendorurl http://iplweb.pl --version `python src/django_bpp/version.py` --eulafile LICENSE

# cel: demo-vm-cleanup
# Usuwa klon demo-maszyny wirutalnej
demo-vm-cleanup:
	VBoxManage unregistervm Demo\ BPP\ `python src/django_bpp/version.py` --delete

vagrantclean:
	vagrant destroy -f

vagrantup:
	vagrant up 

demo-vm: vagrantclean vagrantup staging demo-vm-ansible demo-vm-clone demo-vm-cleanup

# cel: production -DCUSTOMER=... or CUSTOMER=... make production
production: 
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/${CUSTOMER}/ansible/hosts.cfg" ansible/webserver.yml ${ANSIBLE_OPTIONS}

production-update: # "szybka" ścieżka aktualizacji
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/${CUSTOMER}/ansible/hosts.cfg" ansible/webserver.yml -t django-site ${ANSIBLE_OPTIONS}

# cel: live-docs
# Uruchom sphinx-autobuild
live-docs: 
	sphinx-autobuild -p 8080 -D language=pl docs/ docs/_build
