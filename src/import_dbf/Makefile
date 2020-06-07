NAZWA_OBCEJ_JEDNOSTKI=obcy

ifeq ($(DJANGO_BPP_DB_NAME),)
DB_NAME=bpp
else
DB_NAME=$(DJANGO_BPP_DB_NAME)
endif

PSQL=psql -q -t --echo-errors $(DB_NAME) | grep -v "INSERT 0 1"
PSQL_VERBOSE=psql -t --echo-errors -a $(DB_NAME)
PG_DUMP=pg_dump $(DB_NAME)
MANAGE=python ../manage.py
DBF2SQL=python ../../../manage.py dbf2sql
ASSETS_DIR=/tmp/bpp-assets

TABELE=AUT.DB   B_B.DB   B_N.DB   DYS.DB   IXE.DB   JER.DB   KAD.DB   LOC.DB   PBC.DB   PUB.DB   SCI.DB   SYS.DB   WSX.DB   WYD.DB   ldy.dat BIB.DB   B_E.DB   B_P.DB    IXP.DB   JEZ.DB   KBN.DB   PBA.DB   PBD.DB   RTF.DB   S_B.DB   WSY.DB   ixb.db   lis.dat B_A.DB   B_L.DB   B_U.DB   EXT.DB   JED.DB   J_H.DB   KBR.DB   PBB.DB   POZ.DB   SES.DB   USI.DB   WX2.DB   ixn.db

convert-dbfs:
	cd db/bib/ && $(DBF2SQL) $(TABELE)

import-converted-dbfs:
	for tabela in $(TABELE); do psql --echo-errors --quiet -t $(DB_NAME) -f db/bib/$$tabela.sql & done && wait

usun-integracje-autorow:
	echo "begin; delete from bpp_autor_jednostka; delete from bpp_autor;update import_dbf_aut set bpp_autor_id = NULL where bpp_autor_id IS NOT NULL;commit;" | $(PSQL)

get-assets:
	if [ -d $(ASSETS_DIR) ]; then (cd $(ASSETS_DIR) && git pull) || (rm -rfv $(ASSETS_DIR) && git clone https://github.com/iplweb/bpp-assets $(ASSSETS_DIR)) ; else git clone https://github.com/iplweb/bpp-assets $(ASSETS_DIR); fi

integruj-dbf-autorzy:
	$(MANAGE) integruj_dbf --enable-wydzial
	$(MANAGE) integruj_dbf --enable-jednostka
	$(MANAGE) integruj_dbf --enable-autor

importuj-dyscypliny:
	$(MANAGE) importuj_dyscypliny -v0 2017 "/Volumes/Dane zaszyfrowane/UMWroclaw/bpp-assets/dyscypliny/2017.xlsx" & \
		$(MANAGE) importuj_dyscypliny -v0 2018 "/Volumes/Dane zaszyfrowane/UMWroclaw/bpp-assets/dyscypliny/2018.xlsx" & \
		$(MANAGE) importuj_dyscypliny -v0 2019 "/Volumes/Dane zaszyfrowane/UMWroclaw/bpp-assets/dyscypliny/2019.xlsx" & \
		$(MANAGE) importuj_dyscypliny -v0 2020 "/Volumes/Dane zaszyfrowane/UMWroclaw/bpp-assets/dyscypliny/2020.xlsx" & wait

integruj-dbf-publikacje-pre:
	$(MANAGE) integruj_dbf --enable-charakter-kbn-jezyk --charaktery-enrichment-xls $(ASSETS_DIR)/bg-umw/charaktery_formalne.xlsx
	$(MANAGE) integruj_dbf --enable-zrodlo
	$(MANAGE) rozszerz_skroty_zrodel $(ASSETS_DIR)/bg-umw/zrodla.xlsx
	$(PG_DUMP) > pre-integruj-dbf-enable-publikacja.sql

integruj-dbf-publikacje-post:
	$(MANAGE) integruj_dbf --enable-publikacja > integruj-dbf-publikacja-log.txt
	$(MANAGE) integruj_dbf --enable-grupy-punktowe > integruj-dbf-grupy-punktowe-log.txt
	$(MANAGE) integruj_dbf --enable-zatwierdz-podwojne-przypisania
	$(MANAGE) integruj_dbf --enable-b-a
	$(MANAGE) integruj_dbf --enable-przypisz-jednostki

integruj-dbf-publikacje: get-assets integruj-dbf-publikacje-pre integruj-dbf-publikacje-post

przypisz-dyscypliny:
	$(MANAGE) przypisz_dyscypliny -v0 2017 --ustawiaj-pierwsza-gdy-dwie --disable-cache & \
		$(MANAGE) przypisz_dyscypliny -v0 2018 --ustawiaj-pierwsza-gdy-dwie --disable-cache & \
		$(MANAGE) przypisz_dyscypliny -v0 2019 --ustawiaj-pierwsza-gdy-dwie --disable-cache & \
		$(MANAGE) przypisz_dyscypliny -v0 2020 --ustawiaj-pierwsza-gdy-dwie --disable-cache & wait

integruj-dbf: integruj-dbf-autorzy importuj-dyscypliny integruj-dbf-publikacje przypisz-dyscypliny

remove-dbfs:
	echo "select 'drop table '||tablename||';' from pg_tables where tablename like 'import_dbf_%'" | \
	psql -U postgres -d $(DB_NAME) -t | \
	psql -U postgres -d $(DB_NAME)

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

dropdb-createdb:
	dropdb $(DB_NAME) || true
	createdb $(DB_NAME)

recreate-db: dropdb-createdb
	$(MANAGE) migrate

rebuild-cache:
	$(MANAGE) rebuild_cache

create-bib-desc:
	$(MANAGE) integruj_dbf --enable-mapuj-publikacja
	cat sql/translate-bib-desc.sql | $(PSQL)

import-dbf: recreate-db import-converted-dbfs alter-schema create-bib-desc
	$(PG_DUMP) > post-import-dbf.sql

restore-import-dbf-state: dropdb-createdb
	cat post-import-dbf.sql | $(PSQL)

restore-pre-integruj-publikacje-state: dropdb-createdb
	cat pre-integruj-dbf-enable-publikacja.sql | $(PSQL)
	$(MANAGE) migrate

restart-integruj-publikacje: restore-pre-integruj-publikacje-state integruj-dbf-publikacje-post przypisz-dyscypliny  integruj-liste-wydawcow ustaw-obca-jednostke rebuild-cache ustaw-date-aktualizacji wylacz-alfabetyczne-sortowanie-jednostek przenies-sortowanie-jednostek enable-trigger dodaj-aktualnosc

integruj-liste-wydawcow: get-assets
	$(MANAGE) import_wydawca_poziom $(ASSETS_DIR)/poziomy-wydawcow-2017-2020.xlsx
	$(MANAGE) import_wydawca_alias $(ASSETS_DIR)/bg-umw/aliasy_wydawcow.xlsx

ustaw-obca-jednostke:
	$(MANAGE) ustaw_obca_jednostke --wymuszaj "$(NAZWA_OBCEJ_JEDNOSTKI)"

dodaj-aktualnosc:
	$(MANAGE) integruj_dbf --enable-dodaj-aktualnosc

ustaw-date-aktualizacji:
	cat sql/ustaw-date-aktualizacji.sql | $(PSQL_VERBOSE)

wylacz-alfabetyczne-sortowanie-jednostek:
	echo "UPDATE bpp_uczelnia SET sortuj_jednostki_alfabetycznie = 'f'" | $(PSQL_VERBOSE)

przenies-sortowanie-jednostek:
	echo "UPDATE bpp_jednostka SET kolejnosc = import_dbf_jed.sort::integer FROM import_dbf_jed WHERE import_dbf_jed.bpp_jednostka_id = bpp_jednostka.id" | $(PSQL_VERBOSE)

przenies-isbn:
	$(MANAGE) wytnij_isbn_z_uwag --przenies-do-uwag > isbn-przenies.txt
	$(MANAGE) wytnij_isbn_z_uwag --skasuj > isbn-skasuj.txt
	$(MANAGE) wytnij_isbn_z_uwag --skasuj > isbn-skasuj.txt

usun-nieuzywane-charaktery-kbny:
	$(MANAGE) usun_nieuzywane_charaktery_kbny

utworz-doktoraty:
	$(MANAGE) zmien_na_doktorat PD > pd.txt
	$(MANAGE) zmien_na_doktorat ZD > zd.txt

przemapuj-redaktora-na-autora:
	$(MANAGE) zmien_typ_autora PAW
	$(MANAGE) zmien_typ_autora ZAW

integrate: disable-trigger integruj-dbf integruj-liste-wydawcow ustaw-obca-jednostke przenies-isbn utworz-doktoraty \
	przemapuj-redaktora-na-autora \
	rebuild-cache ustaw-date-aktualizacji wylacz-alfabetyczne-sortowanie-jednostek przenies-sortowanie-jednostek \
	enable-trigger dodaj-aktualnosc usun-nieuzywane-charaktery-kbny

set-site-name:
	$(MANAGE) set_site_name --name bpp.umed.wroc.pl --domain bpp.umed.wroc.pl

rebuild: convert-dbfs import-dbf integrate set-site-name

db-name:
	@echo "Te skrypty pracują na bazie danych: $(DB_NAME)"
