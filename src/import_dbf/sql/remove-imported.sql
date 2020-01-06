begin;

delete from bpp_wydawnictwo_ciagle_autor;

delete from bpp_wydawnictwo_zwarte_autor;

delete from bpp_wydawnictwo_zwarte_zewnetrzna_baza_danych;

delete from bpp_autor_jednostka;

delete from bpp_jednostka;

delete from bpp_autor;

delete from bpp_wydawnictwo_ciagle;

delete from bpp_wydawnictwo_zwarte;

update import_dbf_bib set object_id = null, analyzed = false;

delete from import_dbf_bib_desc;

delete from bpp_konferencja;

commit;
