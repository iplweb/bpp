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

ALTER TABLE import_dbf_bib ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;
CREATE UNIQUE INDEX  import_dbf_bib_idt ON  import_dbf_bib(idt);
UPDATE import_dbf_aut SET idt_jed = NULL where idt_jed = '';
UPDATE import_dbf_aut SET orcid_id = NULL where orcid_id = '';
ALTER TABLE import_dbf_aut ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;

ALTER TABLE import_dbf_aut ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
CREATE INDEX ON import_dbf_aut(orcid_id);
CREATE INDEX ON import_dbf_aut(pbn_id);
ALTER TABLE import_dbf_aut ADD COLUMN bpp_autor_id INTEGER;
CREATE UNIQUE INDEX import_dbf_aut_idt ON import_dbf_aut(idt_aut);
create index import_dbf_aut_nazwisko on import_dbf_aut(nazwisko);

ALTER TABLE import_dbf_aut ALTER COLUMN exp_id SET DATA TYPE INT USING exp_id::integer;
update import_dbf_aut set pbn_id = NULL where pbn_id = '';
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
UPDATE import_dbf_b_a SET idt_jed = NULL where idt_jed = '';
ALTER TABLE import_dbf_b_a ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
CREATE INDEX ON import_dbf_b_a(object_id);

ALTER TABLE import_dbf_jed ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
ALTER TABLE import_dbf_jed ADD COLUMN bpp_jednostka_id INTEGER;
CREATE UNIQUE INDEX import_dbf_jed_idt ON import_dbf_jed(idt_jed);

ALTER TABLE import_dbf_b_a ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;
ALTER TABLE import_dbf_b_a ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

UPDATE import_dbf_aut SET ref = NULL where ref = '';
ALTER TABLE import_dbf_aut ALTER COLUMN ref SET DATA TYPE INT USING ref::integer;

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

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~00', 'α'), title = REPLACE(title, 'a~00', 'α') WHERE (tytul_or LIKE '%a~00%' or title LIKE '%a~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'b~00', 'β'), title = REPLACE(title, 'b~00', 'β') WHERE (tytul_or LIKE '%b~00%' or title LIKE '%b~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'g~00', 'γ'), title = REPLACE(title, 'g~00', 'γ') WHERE (tytul_or LIKE '%g~00%' or title LIKE '%g~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'd~00', 'δ'), title = REPLACE(title, 'd~00', 'δ') WHERE (tytul_or LIKE '%d~00%' or title LIKE '%d~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'k~00', 'κ'), title = REPLACE(title, 'k~00', 'κ') WHERE (tytul_or LIKE '%k~00%' or title LIKE '%k~00%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'D~00', 'Δ'), title = REPLACE(title, 'D~00', 'Δ') WHERE (tytul_or LIKE '%D~00%' or title LIKE '%D~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'w~00', 'ω'), title = REPLACE(title, 'w~00', 'ω') WHERE (tytul_or LIKE '%w~00%' or title LIKE '%w~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'W~00', 'Ω'), title = REPLACE(title, 'W~00', 'Ω') WHERE (tytul_or LIKE '%W~00%' or title LIKE '%W~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'r~00', 'ρ'), title = REPLACE(title, 'r~00', 'ρ') WHERE (tytul_or LIKE '%r~00%' or title LIKE '%r~00%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'm~00', 'μ'), title = REPLACE(title, 'm~00', 'μ') WHERE (tytul_or LIKE '%m~00%' or title LIKE '%m~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~00', 'ε'), title = REPLACE(title, 'e~00', 'ε') WHERE (tytul_or LIKE '%e~00%' or title LIKE '%e~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'z~00', 'ζ'), title = REPLACE(title, 'z~00', 'ζ') WHERE (tytul_or LIKE '%z~00%' or title LIKE '%z~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'p~00', 'π'), title = REPLACE(title, 'p~00', 'π') WHERE (tytul_or LIKE '%p~00%' or title LIKE '%p~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'j~00', 'θ'), title = REPLACE(title, 'j~00', 'θ') WHERE (tytul_or LIKE '%j~00%' or title LIKE '%j~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'l~00', 'λ'), title = REPLACE(title, 'l~00', 'λ') WHERE (tytul_or LIKE '%l~00%' or title LIKE '%l~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'l~~00', 'λ'), title = REPLACE(title, 'l~~00', 'λ') WHERE (tytul_or LIKE '%l~~00%' or title LIKE '%l~~00%');

select tytul_or, title from import_dbf_bib where tytul_or like '%~00%' or title like '%~00%';


UPDATE import_dbf_aut SET ref = NULL WHERE ref not in (select idt_aut from import_dbf_aut);

COMMIT;
