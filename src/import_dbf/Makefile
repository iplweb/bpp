PSQL=psql -t --echo-errors bpp | grep -v "INSERT 0 1"
MANAGE=python ../manage.py
DBF2SQL=python ../../../manage.py dbf2sql

rebuild: remove-dbfs import-dbfs alter-schema

TABELE=AUT.DB   B_B.DB   B_N.DB   DYS.DB   IXE.DB   JER.DB   KAD.DB   LOC.DB   PBC.DB   PUB.DB   SCI.DB   SYS.DB   WSX.DB   WYD.DB   ldy.dat BIB.DB   B_E.DB   B_P.DB    IXP.DB   JEZ.DB   KBN.DB   PBA.DB   PBD.DB   RTF.DB   S_B.DB   WSY.DB   ixb.db   lis.dat B_A.DB   B_L.DB   B_U.DB   EXT.DB   JED.DB   J_H.DB   KBR.DB   PBB.DB   POZ.DB   SES.DB   USI.DB   WX2.DB   ixn.db

convert-dbfs:
	cd db/bib/ && $(DBF2SQL) $(TABELE)

import-converted-dbfs:
	for tabela in $(TABELE); do psql --echo-errors --quiet -t bpp -f db/bib/$$tabela.sql & done && wait

integruj-dbf:
	$(MANAGE) integruj_dbf --enable-all -v 3

remove-dbfs:
	echo "select 'drop table '||tablename||';' from pg_tables where tablename like 'import_dbf_%'" | \
	psql -U postgres -d bpp -t | \
	psql -U postgres -d bpp

alter-schema:
	cat sql/alter-schema.sql | $(PSQL)
	cat sql/alter-umw.sql | $(PSQL)

delete-imported-data:
	cat sql/remove-imported.sql | $(PSQL)

create-schema:
	echo "select tablename from pg_tables where tablename like 'import_dbf_%'" | $(PSQL)  | xargs $(MANAGE) inspectdb

recreate-db:
	dropdb bpp
	createdb bpp
	$(MANAGE) migrate

rebuild-db: recreate-db convert-dbfs import-converted-dbfs alter-schema integruj-dbf
