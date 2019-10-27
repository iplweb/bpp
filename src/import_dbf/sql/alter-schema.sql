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

ALTER TABLE import_dbf_aut ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;
ALTER TABLE import_dbf_aut ADD COLUMN bpp_autor_id INTEGER;
CREATE UNIQUE INDEX import_dbf_aut_idt ON import_dbf_aut(idt_aut);

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
CREATE INDEX ON import_dbf_bib(object_id);

-- ALTER TABLE jed ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
ALTER TABLE import_dbf_jed ADD COLUMN bpp_jednostka_id INTEGER;
CREATE UNIQUE INDEX import_dbf_jed_idt ON import_dbf_jed(idt_jed);

ALTER TABLE import_dbf_b_a ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;
ALTER TABLE import_dbf_b_a ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_b_u ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;
ALTER TABLE import_dbf_poz ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_poz ADD COLUMN new_lp INTEGER;
UPDATE import_dbf_poz SET new_lp = ('x' || lpad(lp, 8, '0'))::bit(32)::int ;
ALTER TABLE import_dbf_poz DROP COLUMN lp;
ALTER TABLE import_dbf_poz RENAME new_lp TO lp;
CREATE INDEX import_dbf_poz_idt_idx ON import_dbf_poz(idt);

CREATE UNIQUE INDEX import_dbf_idt_wyd ON import_dbf_wyd(idt_wyd);

COMMIT;
