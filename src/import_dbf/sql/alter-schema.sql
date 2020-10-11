BEGIN;

ALTER TABLE import_dbf_b_a ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_poz ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_b_u ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_ses ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_sys ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_pba ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE import_dbf_pbd ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE import_dbf_rtf ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_s_b ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_lis ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_ext ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_j_h ADD COLUMN IF NOT EXISTS id SERIAL;

ALTER TABLE import_dbf_pbb ADD COLUMN IF NOT EXISTS id SERIAL;


ALTER TABLE import_dbf_b_l ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE import_dbf_b_l ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_usi ALTER COLUMN idt_usi SET DATA TYPE INT USING idt_usi::integer;
ALTER TABLE import_dbf_b_u ALTER COLUMN idt_usi SET DATA TYPE INT USING idt_usi::integer;

ALTER TABLE import_dbf_b_e ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE import_dbf_b_e ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_b_p ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE import_dbf_b_p ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

update import_dbf_bib set idt2 = trim(idt2);
update import_dbf_bib set idt2 = null where idt2 = '';
alter table import_dbf_bib alter column idt2 set data type integer using idt2::integer;

ALTER TABLE import_dbf_bib ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;
CREATE UNIQUE INDEX  import_dbf_bib_idt ON  import_dbf_bib(idt);
UPDATE import_dbf_aut SET idt_jed = NULL where idt_jed = '';
UPDATE import_dbf_aut SET orcid_id = NULL where orcid_id = '';
ALTER TABLE import_dbf_aut ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;

update import_dbf_aut SET idt_jed = trim(idt_jed);
update import_dbf_aut SET idt_jed = null where idt_jed = '';
ALTER TABLE import_dbf_aut ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
CREATE INDEX ON import_dbf_aut(orcid_id);
CREATE INDEX ON import_dbf_aut(pbn_id);
ALTER TABLE import_dbf_aut ADD COLUMN bpp_autor_id INTEGER;
CREATE UNIQUE INDEX import_dbf_aut_idt ON import_dbf_aut(idt_aut);
create index import_dbf_aut_nazwisko on import_dbf_aut(nazwisko);

ALTER TABLE import_dbf_aut ALTER COLUMN exp_id SET DATA TYPE INT USING exp_id::integer;
update import_dbf_aut set pbn_id = trim(pbn_id);
update import_dbf_aut set pbn_id = NULL where pbn_id = '';
-- IN ('', '1981-02-01',  '2004-09-15', '3988552 Za', '3996174 Z',  '3996174 Z');
ALTER TABLE import_dbf_aut ALTER COLUMN pbn_id SET DATA TYPE INT USING pbn_id::integer;

ALTER TABLE import_dbf_jez ADD COLUMN bpp_id INTEGER;
ALTER TABLE import_dbf_kbn ADD COLUMN bpp_id INTEGER;
ALTER TABLE import_dbf_pub ADD COLUMN bpp_id INTEGER;
ALTER TABLE import_dbf_usi ADD COLUMN bpp_id INTEGER;
ALTER TABLE import_dbf_usi ADD COLUMN bpp_wydawca_id INTEGER;
ALTER TABLE import_dbf_usi ADD COLUMN bpp_seria_wydawnicza_id INTEGER;


ALTER TABLE import_dbf_bib ADD COLUMN object_id INTEGER;
ALTER TABLE import_dbf_bib ADD COLUMN content_type_id INTEGER;
ALTER TABLE import_dbf_bib ADD COLUMN analyzed BOOLEAN DEFAULT 'f';
CREATE INDEX ON import_dbf_bib(analyzed);
CREATE INDEX ON import_dbf_bib(object_id);

ALTER TABLE import_dbf_b_a ADD COLUMN object_id INTEGER;
ALTER TABLE import_dbf_b_a ADD COLUMN content_type_id INTEGER;

SELECT * FROM import_dbf_b_a WHERE idt_jed LIKE 'X%';
DELETE FROM import_dbf_b_a WHERE idt_jed LIKE 'X%';

UPDATE import_dbf_b_a SET idt_jed = trim(idt_jed);
UPDATE import_dbf_b_a SET idt_jed = NULL where idt_jed = '';

ALTER TABLE import_dbf_b_a ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
CREATE INDEX ON import_dbf_b_a(object_id);

UPDATE import_dbf_jed SET idt_jed = trim(idt_jed);
ALTER TABLE import_dbf_jed ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
ALTER TABLE import_dbf_jed ADD COLUMN bpp_jednostka_id INTEGER;
CREATE UNIQUE INDEX import_dbf_jed_idt ON import_dbf_jed(idt_jed);

UPDATE import_dbf_b_a SET idt_aut = trim(idt_aut), idt = trim(idt);
ALTER TABLE import_dbf_b_a ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;
ALTER TABLE import_dbf_b_a ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

UPDATE import_dbf_aut SET ref = trim(ref);
UPDATE import_dbf_aut SET ref = NULL where ref = '';
ALTER TABLE import_dbf_aut ALTER COLUMN ref SET DATA TYPE INT USING ref::integer;

SELECT * FROM import_dbf_b_u WHERE idt LIKE 'X%';
DELETE FROM import_dbf_b_u WHERE idt LIKE 'X%';

ALTER TABLE import_dbf_b_u ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;
ALTER TABLE import_dbf_poz ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_poz ADD COLUMN new_lp INTEGER;
UPDATE import_dbf_poz SET new_lp = ('x' || lpad(lp, 8, '0'))::bit(32)::int ;
ALTER TABLE import_dbf_poz DROP COLUMN lp;
ALTER TABLE import_dbf_poz RENAME new_lp TO lp;
CREATE INDEX import_dbf_poz_idt_idx ON import_dbf_poz(idt);

CREATE UNIQUE INDEX import_dbf_idt_wyd ON import_dbf_wyd(idt_wyd);

update import_dbf_aut set idt_jed = (select idt_jed from import_dbf_jed where skrot = '000') where idt_jed is NULL;
update import_dbf_b_a set idt_jed = (select idt_jed from import_dbf_jed where skrot = '000') where idt_jed is NULL;

create index on import_dbf_poz(idt, kod_opisu);
create index on import_dbf_poz(idt, kod_opisu, lp);

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '<UP>', '<sup>') WHERE tytul_or LIKE '%<UP>%';
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '<up>', '<sup>') WHERE tytul_or LIKE '%<up>%';
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '<dn>', '<sub>') WHERE tytul_or LIKE '%<dn>%';
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '<DN>', '<sub>') WHERE tytul_or LIKE '%<DN>%';
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '</UP>', '</sup>') WHERE tytul_or LIKE '%</UP>%';
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '</up>', '</sup>') WHERE tytul_or LIKE '%</up>%';
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '</dn>', '</sub>') WHERE tytul_or LIKE '%</dn>%';
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, '</DN>', '</sub>') WHERE tytul_or LIKE '%</DN>%';

UPDATE import_dbf_bib SET title = REPLACE(title, '<UP>', '<sup>') WHERE title LIKE '%<UP>%';
UPDATE import_dbf_bib SET title = REPLACE(title, '<up>', '<sup>') WHERE title LIKE '%<up>%';
UPDATE import_dbf_bib SET title = REPLACE(title, '<dn>', '<sub>') WHERE title LIKE '%<dn>%';
UPDATE import_dbf_bib SET title = REPLACE(title, '<DN>', '<sub>') WHERE title LIKE '%<DN>%';
UPDATE import_dbf_bib SET title = REPLACE(title, '</UP>', '</sup>') WHERE title LIKE '%</UP>%';
UPDATE import_dbf_bib SET title = REPLACE(title, '</up>', '</sup>') WHERE title LIKE '%</up>%';
UPDATE import_dbf_bib SET title = REPLACE(title, '</dn>', '</sub>') WHERE title LIKE '%</dn>%';
UPDATE import_dbf_bib SET title = REPLACE(title, '</DN>', '</sub>') WHERE title LIKE '%</DN>%';

UPDATE import_dbf_aut SET ref = NULL WHERE ref not in (select idt_aut from import_dbf_aut);

-- Ustawia jednostke 'brak jednostki' tam gdzie jest NULL jako jednostka w tabeli b_a
UPDATE import_dbf_b_a SET idt_jed = (SELECT idt_jed from import_dbf_jed WHERE UPPER(nazwa) = 'BRAK JEDNOSTKI') WHERE idt_jed IS NULL;

alter table import_Dbf_jer add column pk serial;
alter table import_Dbf_b_b add column pk serial;
ALTER TABLE import_dbf_b_b ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_j_h ALTER COLUMN idt_jed_t SET DATA TYPE INT USING idt_jed_t::integer;
ALTER TABLE import_dbf_j_h ALTER COLUMN idt_jed_f SET DATA TYPE INT USING idt_jed_f::integer;

alter table import_Dbf_b_n add column pk serial;
ALTER TABLE import_dbf_b_n ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;


COMMIT;
