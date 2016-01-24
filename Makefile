clean:
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 

build:
	fab prepare
	fab test
	fab build

world:
	vagrant pristine -f master
	vagrant up selenium 
	vagrant up db
	vagrant up staging

buildworld: world build
	@echo "Done!"

wholeworld:
	vagrant pristine -f

buildwholeworld: wholeworld build
	@echo "Done"