-- Odtworzenie rodziny widokow bpp_kronika_* (backward migracji 0499).
--
-- WYGENEROWANE z pg_get_viewdef() na zywym katalogu, nie przepisane recznie.
-- Kolejnosc jest WYMUSZONA grafem zaleznosci: piec widokow lisci, potem
-- bpp_kronika_all_unsorted_view (UNION po nich), na koncu bpp_kronika_view.
--
-- Ta rodzina jest MARTWA (zero konsumentow) i migracja 0499 ja kasuje.
-- Plik istnieje wylacznie po to, zeby ta migracja byla odwracalna.

CREATE VIEW bpp_kronika_wydawnictwo_ciagle_view AS
 SELECT bpp_autor.id AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id AS jednostka_id,
    bpp_wydawnictwo_ciagle.tytul_oryginalny,
    bpp_wydawnictwo_ciagle.tytul_oryginalny_sort,
    bpp_wydawnictwo_ciagle.rok,
    bpp_wydawnictwo_ciagle_autor.kolejnosc,
    'bpp_wydawnictwo_ciagle'::text AS object,
    bpp_wydawnictwo_ciagle.id AS object_pk,
    bpp_wydawnictwo_ciagle.id,
    bpp_wydawnictwo_ciagle.zrodlo_id
   FROM bpp_wydawnictwo_ciagle,
    bpp_wydawnictwo_ciagle_autor,
    bpp_jednostka,
    bpp_zrodlo,
    bpp_autor
  WHERE bpp_wydawnictwo_ciagle_autor.autor_id = bpp_autor.id AND bpp_wydawnictwo_ciagle_autor.rekord_id = bpp_wydawnictwo_ciagle.id AND bpp_wydawnictwo_ciagle_autor.jednostka_id = bpp_jednostka.id AND bpp_zrodlo.id = bpp_wydawnictwo_ciagle.zrodlo_id AND bpp_jednostka.wchodzi_do_rankingu_autorow = true
;

CREATE VIEW bpp_kronika_wydawnictwo_zwarte_view AS
 SELECT bpp_autor.id AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id AS jednostka_id,
    bpp_wydawnictwo_zwarte.tytul_oryginalny,
    bpp_wydawnictwo_zwarte.tytul_oryginalny_sort,
    bpp_wydawnictwo_zwarte.rok,
    bpp_wydawnictwo_zwarte_autor.kolejnosc,
    'bpp_wydawnictwo_zwarte'::text AS object,
    bpp_wydawnictwo_zwarte.id AS object_pk,
    bpp_wydawnictwo_zwarte.id,
    NULL::integer AS zrodlo_id
   FROM bpp_wydawnictwo_zwarte,
    bpp_wydawnictwo_zwarte_autor,
    bpp_jednostka,
    bpp_autor
  WHERE bpp_wydawnictwo_zwarte_autor.autor_id = bpp_autor.id AND bpp_wydawnictwo_zwarte_autor.rekord_id = bpp_wydawnictwo_zwarte.id AND bpp_wydawnictwo_zwarte_autor.jednostka_id = bpp_jednostka.id AND bpp_jednostka.wchodzi_do_rankingu_autorow = true
;

CREATE VIEW bpp_kronika_patent_view AS
 SELECT bpp_autor.id AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id AS jednostka_id,
    bpp_patent.tytul_oryginalny,
    bpp_patent.tytul_oryginalny_sort,
    bpp_patent.rok,
    bpp_patent_autor.kolejnosc,
    'bpp_patent'::text AS object,
    bpp_patent.id AS object_pk,
    bpp_patent.id,
    NULL::integer AS zrodlo_id
   FROM bpp_patent,
    bpp_autor,
    bpp_patent_autor,
    bpp_jednostka
  WHERE bpp_patent_autor.autor_id = bpp_autor.id AND bpp_patent_autor.rekord_id = bpp_patent.id AND bpp_patent_autor.jednostka_id = bpp_jednostka.id AND bpp_jednostka.wchodzi_do_rankingu_autorow = true
;

CREATE VIEW bpp_kronika_praca_doktorska_view AS
 SELECT bpp_praca_doktorska.autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_praca_doktorska.jednostka_id,
    bpp_praca_doktorska.tytul_oryginalny,
    bpp_praca_doktorska.tytul_oryginalny_sort,
    bpp_praca_doktorska.rok,
    1 AS kolejnosc,
    'bpp_praca_doktorska'::text AS object,
    bpp_praca_doktorska.id AS object_pk,
    bpp_praca_doktorska.id,
    NULL::integer AS zrodlo_id
   FROM bpp_praca_doktorska,
    bpp_jednostka,
    bpp_autor
  WHERE bpp_praca_doktorska.autor_id = bpp_autor.id AND bpp_praca_doktorska.jednostka_id = bpp_jednostka.id AND bpp_jednostka.wchodzi_do_rankingu_autorow = true
;

CREATE VIEW bpp_kronika_praca_habilitacyjna_view AS
 SELECT bpp_praca_habilitacyjna.autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_praca_habilitacyjna.jednostka_id,
    bpp_praca_habilitacyjna.tytul_oryginalny,
    bpp_praca_habilitacyjna.tytul_oryginalny_sort,
    bpp_praca_habilitacyjna.rok,
    1 AS kolejnosc,
    'bpp_praca_habilitacyjna'::text AS object,
    bpp_praca_habilitacyjna.id AS object_pk,
    bpp_praca_habilitacyjna.id,
    NULL::integer AS zrodlo_id
   FROM bpp_praca_habilitacyjna,
    bpp_jednostka,
    bpp_autor
  WHERE bpp_praca_habilitacyjna.autor_id = bpp_autor.id AND bpp_praca_habilitacyjna.jednostka_id = bpp_jednostka.id AND bpp_jednostka.wchodzi_do_rankingu_autorow = true
;

CREATE VIEW bpp_kronika_all_unsorted_view AS
 SELECT bpp_kronika_patent_view.autor_id,
    bpp_kronika_patent_view.imiona,
    bpp_kronika_patent_view.nazwisko,
    bpp_kronika_patent_view.jednostka_id,
    bpp_kronika_patent_view.tytul_oryginalny,
    bpp_kronika_patent_view.tytul_oryginalny_sort,
    bpp_kronika_patent_view.rok,
    bpp_kronika_patent_view.kolejnosc,
    bpp_kronika_patent_view.object,
    bpp_kronika_patent_view.object_pk,
    bpp_kronika_patent_view.id,
    bpp_kronika_patent_view.zrodlo_id
   FROM bpp_kronika_patent_view
UNION
 SELECT bpp_kronika_praca_habilitacyjna_view.autor_id,
    bpp_kronika_praca_habilitacyjna_view.imiona,
    bpp_kronika_praca_habilitacyjna_view.nazwisko,
    bpp_kronika_praca_habilitacyjna_view.jednostka_id,
    bpp_kronika_praca_habilitacyjna_view.tytul_oryginalny,
    bpp_kronika_praca_habilitacyjna_view.tytul_oryginalny_sort,
    bpp_kronika_praca_habilitacyjna_view.rok,
    bpp_kronika_praca_habilitacyjna_view.kolejnosc,
    bpp_kronika_praca_habilitacyjna_view.object,
    bpp_kronika_praca_habilitacyjna_view.object_pk,
    bpp_kronika_praca_habilitacyjna_view.id,
    bpp_kronika_praca_habilitacyjna_view.zrodlo_id
   FROM bpp_kronika_praca_habilitacyjna_view
UNION
 SELECT bpp_kronika_praca_doktorska_view.autor_id,
    bpp_kronika_praca_doktorska_view.imiona,
    bpp_kronika_praca_doktorska_view.nazwisko,
    bpp_kronika_praca_doktorska_view.jednostka_id,
    bpp_kronika_praca_doktorska_view.tytul_oryginalny,
    bpp_kronika_praca_doktorska_view.tytul_oryginalny_sort,
    bpp_kronika_praca_doktorska_view.rok,
    bpp_kronika_praca_doktorska_view.kolejnosc,
    bpp_kronika_praca_doktorska_view.object,
    bpp_kronika_praca_doktorska_view.object_pk,
    bpp_kronika_praca_doktorska_view.id,
    bpp_kronika_praca_doktorska_view.zrodlo_id
   FROM bpp_kronika_praca_doktorska_view
UNION
 SELECT bpp_kronika_wydawnictwo_ciagle_view.autor_id,
    bpp_kronika_wydawnictwo_ciagle_view.imiona,
    bpp_kronika_wydawnictwo_ciagle_view.nazwisko,
    bpp_kronika_wydawnictwo_ciagle_view.jednostka_id,
    bpp_kronika_wydawnictwo_ciagle_view.tytul_oryginalny,
    bpp_kronika_wydawnictwo_ciagle_view.tytul_oryginalny_sort,
    bpp_kronika_wydawnictwo_ciagle_view.rok,
    bpp_kronika_wydawnictwo_ciagle_view.kolejnosc,
    bpp_kronika_wydawnictwo_ciagle_view.object,
    bpp_kronika_wydawnictwo_ciagle_view.object_pk,
    bpp_kronika_wydawnictwo_ciagle_view.id,
    bpp_kronika_wydawnictwo_ciagle_view.zrodlo_id
   FROM bpp_kronika_wydawnictwo_ciagle_view
UNION
 SELECT bpp_kronika_wydawnictwo_zwarte_view.autor_id,
    bpp_kronika_wydawnictwo_zwarte_view.imiona,
    bpp_kronika_wydawnictwo_zwarte_view.nazwisko,
    bpp_kronika_wydawnictwo_zwarte_view.jednostka_id,
    bpp_kronika_wydawnictwo_zwarte_view.tytul_oryginalny,
    bpp_kronika_wydawnictwo_zwarte_view.tytul_oryginalny_sort,
    bpp_kronika_wydawnictwo_zwarte_view.rok,
    bpp_kronika_wydawnictwo_zwarte_view.kolejnosc,
    bpp_kronika_wydawnictwo_zwarte_view.object,
    bpp_kronika_wydawnictwo_zwarte_view.object_pk,
    bpp_kronika_wydawnictwo_zwarte_view.id,
    bpp_kronika_wydawnictwo_zwarte_view.zrodlo_id
   FROM bpp_kronika_wydawnictwo_zwarte_view
;

CREATE VIEW bpp_kronika_view AS
 SELECT autor_id,
    imiona,
    nazwisko,
    jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    rok,
    kolejnosc,
    object,
    object_pk,
    id,
    zrodlo_id
   FROM bpp_kronika_all_unsorted_view
  ORDER BY nazwisko, imiona, tytul_oryginalny_sort
;
