BRANCH=`git branch | sed -n '/\* /s///p'`

clean:
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 
	find . -name \*\\.log -print0 | xargs -0 rm -fv 

distclean: clean
	rm -rf build/ dist/ 

vcs:
	fab vcs:${BRANCH}

wheels: 
	fab wheels

prepare-build-environment:
	fab prepare

build-assets:
	fab build_assets

tests:
	fab test

tests-from-scratch: build-assets wheels just-tests
	@echo "Done"

rebuild-staging:
	vagrant pristine -f staging
	yes | ssh-keygen -R bpp-staging.localnet
	yes | ssh-keygen -R bpp-staging
	yes | ssh-keygen -R 192.168.111.101
	yes | ansible-playbook ansible/webserver.yml

staging:
	ansible-playbook ansible/webserver.yml --private-key=.vagrant/machines/staging/virtualbox/private_key

demo-vm-ansible:
	ansible-playbook ansible/demo-vm.yml --private-key=.vagrant/machines/staging/virtualbox/private_key

release: vcs tests-from-scratch build staging
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
