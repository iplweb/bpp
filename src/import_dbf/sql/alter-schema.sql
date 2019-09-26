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

ALTER TABLE import_dbf_b_e ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE import_dbf_b_e ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_b_p ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE import_dbf_b_p ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_bib ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;
CREATE UNIQUE INDEX  import_dbf_bib_idt ON  import_dbf_bib(idt);

ALTER TABLE import_dbf_aut ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;
CREATE UNIQUE INDEX import_dbf_aut_idt ON import_dbf_aut(idt_aut);

-- ALTER TABLE jed ALTER COLUMN idt_jed SET DATA TYPE INT USING idt_jed::integer;
CREATE UNIQUE INDEX import_dbf_jed_idt ON import_dbf_jed(idt_jed);

ALTER TABLE import_dbf_b_a ALTER COLUMN idt_aut SET DATA TYPE INT USING idt_aut::integer;
ALTER TABLE import_dbf_b_a ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

ALTER TABLE import_dbf_b_u ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;
ALTER TABLE import_dbf_poz ALTER COLUMN idt SET DATA TYPE INT USING idt::integer;

CREATE UNIQUE INDEX import_dbf_idt_wyd ON import_dbf_wyd(idt_wyd);

COMMIT;
