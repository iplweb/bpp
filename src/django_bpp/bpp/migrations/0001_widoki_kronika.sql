CREATE OR REPLACE VIEW bpp_kronika_wydawnictwo_ciagle_view AS

  SELECT
    bpp_autor.id                                       AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id                                   AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_wydawnictwo_ciagle.rok,
    bpp_wydawnictwo_ciagle_autor.kolejnosc,
    ('bpp_wydawnictwo_ciagle' :: TEXT COLLATE "pl_PL") AS object,
    bpp_wydawnictwo_ciagle.id                          AS object_pk,
    bpp_wydawnictwo_ciagle.id                          AS id,
    bpp_wydawnictwo_ciagle.zrodlo_id                   AS zrodlo_id


  FROM
      bpp_wydawnictwo_ciagle,
      bpp_wydawnictwo_ciagle_autor,
      bpp_jednostka,
      bpp_zrodlo,
      bpp_autor

  WHERE
    bpp_wydawnictwo_ciagle_autor.autor_id = bpp_autor.id
    AND bpp_wydawnictwo_ciagle_autor.rekord_id = bpp_wydawnictwo_ciagle.id
    AND bpp_wydawnictwo_ciagle_autor.jednostka_id = bpp_jednostka.id
    AND bpp_zrodlo.id = bpp_wydawnictwo_ciagle.zrodlo_id
    AND bpp_jednostka.wchodzi_do_raportow = TRUE;


-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW bpp_kronika_wydawnictwo_zwarte_view AS

  SELECT
    bpp_autor.id                                       AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id                                   AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_wydawnictwo_zwarte.rok,
    bpp_wydawnictwo_zwarte_autor.kolejnosc,
    ('bpp_wydawnictwo_zwarte' :: TEXT COLLATE "pl_PL") AS object,
    bpp_wydawnictwo_zwarte.id                          AS object_pk,
    bpp_wydawnictwo_zwarte.id                          AS id,
    NULL :: INTEGER                                    AS zrodlo_id

  FROM
      bpp_wydawnictwo_zwarte,
      bpp_wydawnictwo_zwarte_autor,
      bpp_jednostka,
      bpp_autor

  WHERE
    bpp_wydawnictwo_zwarte_autor.autor_id = bpp_autor.id
    AND bpp_wydawnictwo_zwarte_autor.rekord_id = bpp_wydawnictwo_zwarte.id
    AND bpp_wydawnictwo_zwarte_autor.jednostka_id = bpp_jednostka.id
    AND bpp_jednostka.wchodzi_do_raportow = TRUE;

-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW bpp_kronika_patent_view AS

  SELECT
    bpp_autor.id                           AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id                       AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_patent.rok,
    bpp_patent_autor.kolejnosc,
    ('bpp_patent' :: TEXT COLLATE "pl_PL") AS object,
    bpp_patent.id                          AS object_pk,
    bpp_patent.id                          AS id,
    NULL :: INTEGER                        AS zrodlo_id

  FROM
      bpp_patent,
      bpp_autor,
      bpp_patent_autor,
      bpp_jednostka

  WHERE
    bpp_patent_autor.autor_id = bpp_autor.id
    AND bpp_patent_autor.rekord_id = bpp_patent.id
    AND bpp_patent_autor.jednostka_id = bpp_jednostka.id
    AND bpp_jednostka.wchodzi_do_raportow = TRUE;

-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW bpp_kronika_praca_doktorska_view AS

  SELECT
    bpp_praca_doktorska.autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_praca_doktorska.jednostka_id                AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_praca_doktorska.rok,
    1                                               AS kolejnosc,
    ('bpp_praca_doktorska' :: TEXT COLLATE "pl_PL") AS object,
    bpp_praca_doktorska.id                          AS object_pk,
    bpp_praca_doktorska.id                          AS id,
    NULL :: INTEGER                                 AS zrodlo_id


  FROM
      bpp_praca_doktorska,
      bpp_jednostka,
      bpp_autor

  WHERE
    bpp_praca_doktorska.autor_id = bpp_autor.id
    AND bpp_praca_doktorska.jednostka_id = bpp_jednostka.id
    AND bpp_jednostka.wchodzi_do_raportow = TRUE;


-- --------------------------------------------------------------------------


CREATE OR REPLACE VIEW bpp_kronika_praca_habilitacyjna_view AS

  SELECT
    bpp_praca_habilitacyjna.autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_praca_habilitacyjna.jednostka_id                AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_praca_habilitacyjna.rok,
    1                                                   AS kolejnosc,
    ('bpp_praca_habilitacyjna' :: TEXT COLLATE "pl_PL") AS object,
    bpp_praca_habilitacyjna.id                          AS object_pk,
    bpp_praca_habilitacyjna.id                          AS id,
    NULL :: INTEGER                                     AS zrodlo_id


  FROM
      bpp_praca_habilitacyjna,
      bpp_jednostka,
      bpp_autor

  WHERE
    bpp_praca_habilitacyjna.autor_id = bpp_autor.id
    AND bpp_praca_habilitacyjna.jednostka_id = bpp_jednostka.id
    AND bpp_jednostka.wchodzi_do_raportow = TRUE;


-- -------------------------------------------------------------------------

CREATE OR REPLACE VIEW bpp_kronika_all_unsorted_view AS
  SELECT
    *
  FROM bpp_kronika_patent_view
  UNION
  SELECT
    *
  FROM bpp_kronika_praca_habilitacyjna_view
  UNION
  SELECT
    *
  FROM bpp_kronika_praca_doktorska_view
  UNION
  SELECT
    *
  FROM bpp_kronika_wydawnictwo_ciagle_view
  UNION
  SELECT
    *
  FROM bpp_kronika_wydawnictwo_zwarte_view;


CREATE OR REPLACE VIEW bpp_kronika_view AS
  SELECT
    *
  FROM bpp_kronika_all_unsorted_view
  ORDER BY nazwisko, imiona, tytul_oryginalny_sort;

--
-- CREATE OR REPLACE VIEW bpp_kronika_numerki_view AS
--   SELECT
--     rok,
--     object,
--     object_pk,
--     nazwisko,
--     imiona,
--     cut_tytul(tytul_oryginalny),
--     row_number()
--     OVER (ORDER BY nazwisko, imiona, cut_tytul(tytul_oryginalny)) AS id
--   FROM bpp_kronika_view
--   WHERE kolejnosc = 1;