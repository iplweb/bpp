BEGIN;

CREATE OR REPLACE VIEW bpp_zewnetrzne_bazy_wydawnictwo_ciagle_view AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'wydawnictwo_ciagle'),
    bpp_wydawnictwo_ciagle_zewnetrzna_baza_danych.rekord_id
    ] :: INTEGER [2] AS rekord_id,

    baza_id,
    INFO

  FROM bpp_wydawnictwo_ciagle_zewnetrzna_baza_danych;


CREATE OR REPLACE VIEW bpp_zewnetrzne_bazy_view AS

  SELECT *
  FROM bpp_zewnetrzne_bazy_wydawnictwo_ciagle_view;

COMMIT;
