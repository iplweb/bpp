clean:
	find . -name \*~ -print0 | xargs -0 rm -fv 
	find . -name \*pyc -print0 | xargs -0 rm -fv 

build:
	fab prepare
	fab test
	fab build

world:
	vagrant pristine -f

buildworld: world build
	@echo "Done"