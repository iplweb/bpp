BEGIN;

UPDATE import_dbf_wyd SET nazwa = 'BRAK DANYCH 2' WHERE skrot = 'BD';

ALTER TABLE bpp_autor_jednostka
    DROP CONSTRAINT IF EXISTS bez_dat_do_w_przyszlosci;

UPDATE import_dbf_b_a SET lp = '004' WHERE idt = 15069 and lp = '003' and idt_aut = 518;
UPDATE import_dbf_b_a SET lp = '005' WHERE idt = 15069 and lp = '004' and idt_aut = 6757;

UPDATE import_dbf_b_a SET lp = lp || '1' WHERE idt = 17643;
UPDATE import_dbf_b_a SET lp = '0142' WHERE idt = 17643 AND idt_aut = 16714;

DELETE FROM  import_dbf_b_a WHERE  idt = 17980 AND lp = '002' AND idt_aut = 16824;
INSERT INTO import_dbf_b_a(idt, lp, idt_aut, idt_jed, afiliacja) VALUES(17980, '002', 16824, 123, '*');

SELECT 'PRZYPISANIA Z TAKIM SAMYM LP W TABELI B_A';
select tytul_or from import_dbf_bib where idt  in (select idt from import_dbf_b_a group by idt, lp having count(*) > 1);

COMMIT;