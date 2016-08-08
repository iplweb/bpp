BRANCH=`git branch | sed -n '/\* /s///p'`

clean:
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 

boot:
	vagrant up

vcs:
	fab vcs:${BRANCH}

wheels: 
	fab wheels

prepare:
	fab prepare

tests:  vcs wheels prepare
	fab test

build:
	fab build

rebuild-staging:
	vagrant pristine -f staging
	yes | ssh-keygen -R bpp-staging.localnet
	yes | ssh-keygen -R bpp-staging
	yes | ssh-keygen -R 192.168.111.101
	yes | ansible-playbook ansible/webserver.yml

staging:
	ansible-playbook ansible/webserver.yml

full-build: vcs tests build staging
	@echo "Done"

small-build: vcs build staging
	@echo "Done"

local-build:
	buildscripts/prepare-build-env.sh
	buildscripts/run-tests.sh

machines: 
	vagrant pristine -f

buildworld: machines build
	@echo "Done"

new-patch: clean
	bumpversion patch 
	git push
	git push --tags

release: new-patch full-build
	@echo "Done"

download-db:
	fab -H zarzadca@bpp.umlub.pl download_db

rebuild-from-downloaded:
	fab -H zarzadca@bpp.umlub.pl download_db:restore=True,cleanup=False,recreate=True,download=False

production:
	ansible-playbook -i "/Volumes/Dane zaszyfrowane/Biblioteka Glowna/ansible/hosts.cfg" ansible/webserver.yml

upload-db-to-staging:
	fab -pvagrant -H vagrant@bpp-staging.localnet upload_db:zarzadca@bpp.umlub.pl-bpp.backup,staging-bpp,staging-bpp
