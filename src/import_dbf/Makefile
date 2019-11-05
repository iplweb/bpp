PSQL=psql -t --echo-errors bpp | grep -v "INSERT 0 1"
MANAGE=python ../manage.py
DBF2SQL=python ../../../manage.py dbf2sql

rebuild: remove-dbfs import-dbfs alter-schema

TABELE=AUT.DB   B_B.DB   B_N.DB   DYS.DB   IXE.DB   JER.DB   KAD.DB   LOC.DB   PBC.DB   PUB.DB   SCI.DB   SYS.DB   WSX.DB   WYD.DB   ldy.dat BIB.DB   B_E.DB   B_P.DB    IXP.DB   JEZ.DB   KBN.DB   PBA.DB   PBD.DB   RTF.DB   S_B.DB   WSY.DB   ixb.db   lis.dat B_A.DB   B_L.DB   B_U.DB   EXT.DB   JED.DB   J_H.DB   KBR.DB   PBB.DB   POZ.DB   SES.DB   USI.DB   WX2.DB   ixn.db

convert-dbfs:
	cd db/bib/ && $(DBF2SQL) $(TABELE)

import-converted-dbfs:
	for tabela in $(TABELE); do psql --echo-errors --quiet -t bpp -f db/bib/$$tabela.sql & done && wait

usun-integracje-autorow:
	echo "begin; delete from bpp_autor_jednostka; delete from bpp_autor;update import_dbf_aut set bpp_autor_id = NULL where bpp_autor_id IS NOT NULL;commit;" | $(PSQL)

integruj-dbf-autorzy:

	$(MANAGE) integruj_dbf --enable-wydzial
	$(MANAGE) integruj_dbf --enable-jednostka
	$(MANAGE) integruj_dbf --enable-autor

integruj-dbf-publikacje:
	$(MANAGE) integruj_dbf --enable-charakter-kbn-jezyk
	$(MANAGE) integruj_dbf --enable-zrodlo
	$(MANAGE) integruj_dbf --enable-publikacja
	$(MANAGE) integruj_dbf --enable-b-a
	$(MANAGE) integruj_dbf --enable-przypisz-jednostki

integruj-dbf: integruj-dbf-autorzy integruj-dbf-publikacje


remove-dbfs:
	echo "select 'drop table '||tablename||';' from pg_tables where tablename like 'import_dbf_%'" | \
	psql -U postgres -d bpp -t | \
	psql -U postgres -d bpp

alter-schema:
	cat sql/alter-schema.sql | $(PSQL)
	cat sql/alter-umw.sql | $(PSQL)

delete-imported-data:
	cat sql/remove-imported.sql | $(PSQL)

disable-trigger:
	cat sql/disable-trigger.sql | $(PSQL)

enable-trigger:
	cat sql/enable-trigger.sql | $(PSQL)


create-schema:
	echo "select tablename from pg_tables where tablename like 'import_dbf_%'" | $(PSQL)  | xargs $(MANAGE) inspectdb

recreate-db:
	dropdb bpp || true
	createdb bpp
	$(MANAGE) migrate

rebuild-cache:
	$(MANAGE) rebuild_cache

pre-import: recreate-db convert-dbfs import-converted-dbfs alter-schema

import: disable-trigger integruj-dbf rebuild-cache enable-trigger

rebuild-db: pre-import import
