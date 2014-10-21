ifeq ($(OS),Windows_NT)
PYTHON=./venv/scripts/python.exe
else
PYTHON=python
endif

MANAGE=${PYTHON} manage.py
LOADDATA=${MANAGE} loaddata
MIGRATE=${MANAGE} migrate --noinput --traceback

ifeq ($(HOSTNAME),pirx)
PGUSER=aml
PGPASSWORD="1g97r8mhvfsdaoighq329thadsfasd"
PGDATABASE=b_med
PGHOST=127.0.0.1
else
ifeq ($(HOSTNAME),jenkins)
PGHOST?=localhost
else
PGHOST?=bpplocal
endif
endif
PGUSER?=postgres
PGOPTS=-U ${PGUSER} -h ${PGHOST}
DB=db ${PGOPTS}

CREATEDB=create${DB}
DROPDB=drop${DB}
CREATESUPERUSER=/usr/sbin/createuser ${PGOPTS} -s
DROPUSER=dropuser ${PGOPTS}
PSQL=psql ${PGOPTS}

DJANGO_BPP_DATABASE_NAME?=django_bpp

all:
	@echo "make rebuild -- odbudowanie bazy z PostgreSQL"
	@echo "make import_upstream -- zgranie bazy z serwera BPP UM do lokalnego PostgreSQL"

rebuild: rebuilddb loaddata import staticfiles
	@echo "Zrobione!"

download_upstream:
	fab download_dump

rebuild_postgresql:
	-${CREATESUPERUSER} aml
	-${DROPDB} b_med
	${CREATEDB} b_med
	gzip -cd dbdump@bpp.umlub.pl/dump.gz | ${PSQL} b_med

import_upstream: download_upstream rebuild_postgresql
	@echo "Zrobione!"

migrate:
	${MIGRATE}

removedb: recreatedb
	@echo "DB removed"

recreatedb:
	-${DROPDB} ${DJANGO_BPP_DATABASE_NAME}
	${CREATEDB} ${DJANGO_BPP_DATABASE_NAME}

rebuilddb: removedb migrate
	${MANAGE} load_customized_sql
	@echo "DONE!"

loaddata:
	${LOADDATA} jezyk.json
	${LOADDATA} status_korekty.json
	${LOADDATA} charakter_formalny.json
	${LOADDATA} typ_kbn.json
	${LOADDATA} tytul.json
	${LOADDATA} funkcja_autora.json
	${LOADDATA} zrodlo_informacji.json
	${LOADDATA} rodzaj_zrodla.json
	${LOADDATA} plec.json
	${LOADDATA} typ_odpowiedzialnosci.json
	${LOADDATA} um_lublin_uczelnia.json
	${LOADDATA} um_lublin_wydzial.json
	${LOADDATA} um_lublin_charakter_formalny.json

	${MANAGE} install_file files/data/uml/logo.png Uczelnia 1 logo_www
	${MANAGE} install_file files/data/uml/favicon.ico Uczelnia 1 favicon_ico



import:
	${MANAGE} run_import --traceback --cpu=1

import-clean: rebuilddb loaddata import
	@echo done

import_opi_2012:
	${MANAGE} import_afiliacje_2012 --traceback data\uml\workplaces
	${MANAGE} import_imiona_2012 --traceback data\uml\names
	${MANAGE} export_opi_2012 --traceback

rebuild-django_bpp:
	sudo supervisorctl stop bpp.umlub.pl:*
	
	sudo /usr/bin/service pgbouncer stop
	
	bash -c ". /usr/local/bin/virtualenvwrapper.sh && \
		export WORKON_HOME=~/websites && \
		workon bpp.umlub.pl && unset PGPASSWORD && \
		export PGHOST=pirx PGUSER=zarzadca && \
		make recreatedb"
	
	sudo /usr/bin/service pgbouncer start
	
	bash -c ". /usr/local/bin/virtualenvwrapper.sh && \
		export WORKON_HOME=~/websites && \
		workon bpp.umlub.pl && unset PGPASSWORD && \
		export PGHOST=pirx PGUSER=zarzadca && \
		make syncdb migrate loaddata import"
	
	sudo /usr/bin/service pgbouncer start
	
	sudo supervisorctl start bpp.umlub.pl:*


# test crawler:
# crawl:
#	${MANAGE} crawl
#	${MANAGE} crawl --auth username:sysdba,password:11t3h4cc3s /admin

# stare
# import_afiliacje:
# 	${MANAGE} import_afiliacje "c:\users\dotz\desktop" --traceback

