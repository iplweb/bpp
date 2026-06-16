-- Pożegnanie z kolacją libc public."pl_PL" (forward).
--
-- Kolacja (0001_collation.sql: CREATE COLLATION "pl_PL" locale='pl_PL.UTF-8')
-- to kolacja libc, której stockowy/oficjalny obraz postgres NIE potrafi
-- dostarczyć (generuje tylko en_US.UTF-8). Projekt migruje z własnego
-- iplweb/bpp_dbserver na stockowego postgresa, więc kolacja musi zniknąć.
--
-- Była użyta WYŁĄCZNIE na stałych literałach ASCII ('bpp_patent'::text COLLATE
-- "pl_PL") w 5 bazowych widokach bpp_kronika_*_view (no-op dla sortowania).
-- UWAGA: kolacja propaguje się W GÓRĘ łańcucha widoków przez `SELECT *`:
--     bpp_kronika_{patent,praca_doktorska,praca_habilitacyjna,
--                  wydawnictwo_ciagle,wydawnictwo_zwarte}_view   (kolumna object)
--         -> bpp_kronika_all_unsorted_view   (UNION 5 powyższych)
--         -> bpp_kronika_view                (SELECT * ... ORDER BY)
-- więc kolumna `object` w widokach pochodnych też zależy od kolacji.
--
-- DLACZEGO DROP + CREATE, a nie CREATE OR REPLACE: PostgreSQL odmawia zmiany
-- kolacji kolumny widoku przez CREATE OR REPLACE VIEW ("cannot change collation
-- of view column"). Trzeba więc skasować cały łańcuch (od góry) i odtworzyć go
-- bez COLLATE (od dołu), a na końcu zrzucić samą kolację.
--
-- Idempotencja: DROP VIEW IF EXISTS + DROP COLLATION IF EXISTS. Na świeżych
-- instalacjach z (już zedytowanego) baseline widoki są bez COLLATE, a kolacji
-- nie ma → po prostu odtwarzamy widoki w identycznym kształcie i DROP COLLATION
-- jest no-opem. Na starych klastrach (z obrazu z locale) — usuwamy COLLATE i
-- kolację. BEZ CASCADE: drop w kolejności zależności, więc nieoczekiwany
-- zależny obiekt wywali migrację głośno zamiast zostać po cichu skasowany.

-- 1) Skasuj łańcuch od góry (zależne najpierw).
DROP VIEW IF EXISTS bpp_kronika_view;
DROP VIEW IF EXISTS bpp_kronika_all_unsorted_view;
DROP VIEW IF EXISTS bpp_kronika_patent_view;
DROP VIEW IF EXISTS bpp_kronika_praca_doktorska_view;
DROP VIEW IF EXISTS bpp_kronika_praca_habilitacyjna_view;
DROP VIEW IF EXISTS bpp_kronika_wydawnictwo_ciagle_view;
DROP VIEW IF EXISTS bpp_kronika_wydawnictwo_zwarte_view;

-- 2) Odtwórz widoki bazowe BEZ COLLATE (od dołu łańcucha).
CREATE VIEW bpp_kronika_wydawnictwo_ciagle_view AS
  SELECT
    bpp_autor.id                                       AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id                                   AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_wydawnictwo_ciagle.rok,
    bpp_wydawnictwo_ciagle_autor.kolejnosc,
    ('bpp_wydawnictwo_ciagle' :: TEXT)                 AS object,
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

CREATE VIEW bpp_kronika_wydawnictwo_zwarte_view AS
  SELECT
    bpp_autor.id                                       AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id                                   AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_wydawnictwo_zwarte.rok,
    bpp_wydawnictwo_zwarte_autor.kolejnosc,
    ('bpp_wydawnictwo_zwarte' :: TEXT)                 AS object,
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

CREATE VIEW bpp_kronika_patent_view AS
  SELECT
    bpp_autor.id                           AS autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_jednostka.id                       AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_patent.rok,
    bpp_patent_autor.kolejnosc,
    ('bpp_patent' :: TEXT)                 AS object,
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

CREATE VIEW bpp_kronika_praca_doktorska_view AS
  SELECT
    bpp_praca_doktorska.autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_praca_doktorska.jednostka_id                AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_praca_doktorska.rok,
    1                                               AS kolejnosc,
    ('bpp_praca_doktorska' :: TEXT)                 AS object,
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

CREATE VIEW bpp_kronika_praca_habilitacyjna_view AS
  SELECT
    bpp_praca_habilitacyjna.autor_id,
    bpp_autor.imiona,
    bpp_autor.nazwisko,
    bpp_praca_habilitacyjna.jednostka_id                AS jednostka_id,
    tytul_oryginalny,
    tytul_oryginalny_sort,
    bpp_praca_habilitacyjna.rok,
    1                                                   AS kolejnosc,
    ('bpp_praca_habilitacyjna' :: TEXT)                 AS object,
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

-- 3) Odtwórz widoki pochodne (kolumna object dziedziczy teraz domyślną kolację).
CREATE VIEW bpp_kronika_all_unsorted_view AS
  SELECT * FROM bpp_kronika_patent_view
  UNION
  SELECT * FROM bpp_kronika_praca_habilitacyjna_view
  UNION
  SELECT * FROM bpp_kronika_praca_doktorska_view
  UNION
  SELECT * FROM bpp_kronika_wydawnictwo_ciagle_view
  UNION
  SELECT * FROM bpp_kronika_wydawnictwo_zwarte_view;

CREATE VIEW bpp_kronika_view AS
  SELECT * FROM bpp_kronika_all_unsorted_view
  ORDER BY nazwisko, imiona, tytul_oryginalny_sort;

-- 4) Teraz nikt już nie zależy od kolacji — zrzuć ją.
DROP COLLATION IF EXISTS public."pl_PL";
