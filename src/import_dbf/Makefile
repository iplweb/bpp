PSQL=psql -q -t --echo-errors bpp | grep -v "INSERT 0 1"
PSQL_VERBOSE=psql -t --echo-errors -a bpp
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

importuj-dyscypliny:
	$(MANAGE) importuj_dyscypliny -v0 2017 /Volumes/Dane\ zaszyfrowane/UMWroclaw/dyscypliny_BPP.xlsx
	$(MANAGE) importuj_dyscypliny -v0 2018 /Volumes/Dane\ zaszyfrowane/UMWroclaw/dyscypliny_BPP.xlsx
	$(MANAGE) importuj_dyscypliny -v0 2019 /Volumes/Dane\ zaszyfrowane/UMWroclaw/dyscypliny_BPP.xlsx
	$(MANAGE) importuj_dyscypliny -v0 2020 /Volumes/Dane\ zaszyfrowane/UMWroclaw/dyscypliny_BPP.xlsx

integruj-dbf-publikacje:
	$(MANAGE) integruj_dbf --enable-charakter-kbn-jezyk --charaktery-enrichment-xls /Volumes/Dane\ zaszyfrowane/UMWroclaw/charaktery.xlsx
	$(MANAGE) integruj_dbf --enable-zrodlo
	$(MANAGE) integruj_dbf --enable-publikacja > integruj-dbf-publikacja-log.txt
	$(MANAGE) integruj_dbf --enable-zatwierdz-podwojne-przypisania
	$(MANAGE) integruj_dbf --enable-b-a
	$(MANAGE) integruj_dbf --enable-przypisz-jednostki

przypisz-dyscypliny:
	$(MANAGE) przypisz_dyscypliny -v0 2017 --ustawiaj-pierwsza-gdy-dwie --disable-cache
	$(MANAGE) przypisz_dyscypliny -v0 2018 --ustawiaj-pierwsza-gdy-dwie --disable-cache
	$(MANAGE) przypisz_dyscypliny -v0 2019 --ustawiaj-pierwsza-gdy-dwie --disable-cache
	$(MANAGE) przypisz_dyscypliny -v0 2020 --ustawiaj-pierwsza-gdy-dwie --disable-cache

integruj-dbf: integruj-dbf-autorzy importuj-dyscypliny integruj-dbf-publikacje przypisz-dyscypliny

remove-dbfs:
	echo "select 'drop table '||tablename||';' from pg_tables where tablename like 'import_dbf_%'" | \
	psql -U postgres -d bpp -t | \
	psql -U postgres -d bpp

alter-schema:
	cat sql/alter-schema.sql | $(PSQL_VERBOSE)
	cat sql/translate-title.sql | $(PSQL)
	cat sql/translate-autor.sql | $(PSQL)
	cat sql/translate-poz.sql | $(PSQL)
	cat sql/translate-usi.sql | $(PSQL)
	cat sql/translate-zrodlo.sql | $(PSQL)
	cat sql/alter-umw.sql | $(PSQL)

delete-imported-data:
	cat sql/remove-imported.sql | $(PSQL)

disable-trigger:
	cat sql/disable-trigger.sql | $(PSQL_VERBOSE)

enable-trigger:
	cat sql/enable-trigger.sql | $(PSQL_VERBOSE)


create-schema:
	echo "select tablename from pg_tables where tablename like 'import_dbf_%'" | $(PSQL)  | xargs $(MANAGE) inspectdb

recreate-db:
	dropdb bpp || true
	createdb bpp
	$(MANAGE) migrate

rebuild-cache:
	$(MANAGE) rebuild_cache

import-dbf: recreate-db import-converted-dbfs alter-schema

integrate: disable-trigger integruj-dbf rebuild-cache enable-trigger

rebuild: convert-dbfs import-dbf integrate
