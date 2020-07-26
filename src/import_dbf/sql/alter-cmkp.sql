BEGIN;

UPDATE import_dbf_wyd SET nazwa = 'BRAK DANYCH 2' WHERE skrot = 'BD';

ALTER TABLE bpp_autor_jednostka
    DROP CONSTRAINT IF EXISTS bez_dat_do_w_przyszlosci;

COMMIT;