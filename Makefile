clean:
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 


boot-machines:
	vagrant up

vcs: boot-machines
	fab vcs

prepare: vcs
	fab wheels
	fab prepare

tests: prepare
	fab test

full-build: tests
	fab build
	ansible-playbook ansible/staging.yml

small-build:
	fab build
	ansible-playbook ansible/staging.yml

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

release: new-patch
	fab build

download-db:
	fab -H zarzadca@bpp.umlub.pl download_db

