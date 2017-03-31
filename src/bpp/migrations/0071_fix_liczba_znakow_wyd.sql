BEGIN;

DROP VIEW bpp_wydawnictwo_ciagle_view CASCADE;
CREATE VIEW bpp_wydawnictwo_ciagle_view AS SELECT
  django_content_type.id::text || '_' || bpp_wydawnictwo_ciagle.id::text AS fake_id,

  django_content_type.id AS content_type_id,
  bpp_wydawnictwo_ciagle.id AS object_id,

  tytul_oryginalny,
  tytul,
  search_index,

  rok,

  jezyk_id,
  typ_kbn_id,

  charakter_formalny_id,

  zrodlo_id,

  NULL::text AS wydawnictwo,

  slowa_kluczowe,
  informacje,
  szczegoly,
  uwagi,

  impact_factor,
  punkty_kbn,
  index_copernicus,
  punktacja_wewnetrzna,

  kc_impact_factor,
  kc_punkty_kbn,
  kc_index_copernicus,

  adnotacje,

  utworzono,
  ostatnio_zmieniony,

  tytul_oryginalny_sort,
  opis_bibliograficzny_cache,
  opis_bibliograficzny_autorzy_cache,
  opis_bibliograficzny_zapisani_autorzy_cache,

  afiliowana,
  recenzowana,

  liczba_znakow_wydawniczych,

  www

FROM
  bpp_wydawnictwo_ciagle, django_content_type
WHERE
  django_content_type.app_label = 'bpp' AND
  django_content_type.model = 'wydawnictwo_ciagle';


CREATE VIEW bpp_rekord AS
  SELECT * FROM bpp_wydawnictwo_ciagle_view
    UNION
      SELECT * FROM bpp_wydawnictwo_zwarte_view
        UNION
          SELECT * FROM bpp_patent_view
            UNION
              SELECT * FROM bpp_praca_doktorska_view
                UNION
                  SELECT * FROM bpp_praca_habilitacyjna_view;

DELETE FROM bpp_rekord_mat;
INSERT INTO bpp_rekord_mat SELECT * FROM bpp_rekord;

COMMIT;