PSQL=psql --echo-errors | grep -v "INSERT 0 1"
MANAGE=python ../manage.py
IMPORT_DBF=$(MANAGE) import_dbf 

all: import-dbfs create-schema

import-dbfs:
	$(IMPORT_DBF) db/bib/BIB.DB | $(PSQL)
	$(IMPORT_DBF) db/bib/B_A.DB | $(PSQL)
	$(IMPORT_DBF) db/bib/AUT.DB | $(PSQL)
	$(IMPORT_DBF) db/bib/POZ.DB | $(PSQL)
	$(IMPORT_DBF) db/bib/B_U.DB | $(PSQL)
	$(IMPORT_DBF) db/bib/USI.DB | $(PSQL)
	$(IMPORT_DBF) db/bib/SES.DB | $(PSQL)
	$(IMPORT_DBF) db/bib/JED.DB | $(PSQL)

remove-dbfs:
	cat sql/remove-dbfs.sql | $(PSQL)

alter-schema:
	cat sql/alter-schemq.sql | $(PSQL)

create-schema:
	$(MANAGE) inspectdb bib b_a aut poz b_u usi ses jed
