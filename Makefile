clean:
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 


boot:
	vagrant up

vcs:
	fab vcs

wheels: 
	fab wheels

prepare:
	fab prepare

tests:  vcs wheels prepare
	fab test

build:
	fab build

staging:
	ansible-playbook ansible/staging.yml

full-build: vcs tests build staging
	@echo "Done"

small-build: vcs build staging
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

