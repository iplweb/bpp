BEGIN;

DROP VIEW IF EXISTS bpp_wydawnictwo_ciagle_view  CASCADE;
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

  '0'::integer AS liczba_znakow_wydawniczych,

  www

FROM
  bpp_wydawnictwo_ciagle, django_content_type
WHERE
  django_content_type.app_label = 'bpp' AND
  django_content_type.model = 'wydawnictwo_ciagle';




DROP VIEW IF EXISTS bpp_wydawnictwo_zwarte_view  CASCADE;
CREATE VIEW bpp_wydawnictwo_zwarte_view AS SELECT
  django_content_type.id::text || '_' || bpp_wydawnictwo_zwarte.id::text AS fake_id,

  django_content_type.id AS content_type_id,
  bpp_wydawnictwo_zwarte.id AS object_id,

  tytul_oryginalny,
  tytul,
  search_index,

  rok,

  jezyk_id,
  typ_kbn_id,

  charakter_formalny_id,

  NULL::integer AS zrodlo_id,

  wydawnictwo,

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
  bpp_wydawnictwo_zwarte, django_content_type
WHERE
  django_content_type.app_label = 'bpp' AND
  django_content_type.model = 'wydawnictwo_zwarte';

  
DROP VIEW IF EXISTS bpp_patent_view  CASCADE;

CREATE VIEW bpp_patent_view AS SELECT
  django_content_type.id::text || '_' || bpp_patent.id::text AS fake_id,

  django_content_type.id AS content_type_id,
  bpp_patent.id AS object_id,

  tytul_oryginalny,
  NULL::text AS tytul,
  search_index,

  rok,

  bpp_jezyk.id AS jezyk_id,
  bpp_typ_kbn.id AS typ_kbn_id,

  bpp_charakter_formalny.id AS charakter_formalny_id,

  NULL::integer AS zrodlo_id,

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

  '0'::integer AS liczba_znakow_wydawniczych,

  www

FROM
  bpp_patent, django_content_type, bpp_jezyk, bpp_charakter_formalny, bpp_typ_kbn
WHERE
  django_content_type.app_label = 'bpp' AND
  django_content_type.model = 'patent' AND
  bpp_jezyk.skrot = 'pol.' AND
  bpp_typ_kbn.skrot = 'PO' AND
  bpp_charakter_formalny.skrot = 'PAT';




DROP VIEW IF EXISTS bpp_praca_doktorska_view  CASCADE;

CREATE VIEW bpp_praca_doktorska_view AS SELECT
  django_content_type.id::text || '_' || bpp_praca_doktorska.id::text AS fake_id,

  django_content_type.id AS content_type_id,
  bpp_praca_doktorska.id AS object_id,

  tytul_oryginalny,
  tytul,
  search_index,

  rok,

  jezyk_id,
  typ_kbn_id,

  bpp_charakter_formalny.id AS charakter_formalny_id,

  NULL::integer AS zrodlo_id,

  wydawnictwo,

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

  '0'::integer AS liczba_znakow_wydawniczych,

  www

FROM
  bpp_praca_doktorska, django_content_type, bpp_charakter_formalny
WHERE
  django_content_type.app_label = 'bpp' AND
  django_content_type.model = 'praca_doktorska' AND
  bpp_charakter_formalny.skrot = 'D';




DROP VIEW IF EXISTS bpp_praca_habilitacyjna_view  CASCADE;

CREATE VIEW bpp_praca_habilitacyjna_view AS SELECT
  django_content_type.id::text || '_' || bpp_praca_habilitacyjna.id::text AS fake_id,

  django_content_type.id AS content_type_id,
  bpp_praca_habilitacyjna.id AS object_id,

  tytul_oryginalny,
  tytul,
  search_index,

  rok,

  jezyk_id,
  typ_kbn_id,

  bpp_charakter_formalny.id AS charakter_formalny_id,

  NULL::integer AS zrodlo_id,

  wydawnictwo,

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

  '0'::integer AS liczba_znakow_wydawniczych,

  www

FROM
  bpp_praca_habilitacyjna, django_content_type, bpp_charakter_formalny
WHERE
  django_content_type.app_label = 'bpp' AND
  django_content_type.model = 'praca_habilitacyjna' AND
  bpp_charakter_formalny.skrot = 'H';




DROP VIEW IF EXISTS bpp_rekord CASCADE;

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




  
COMMIT;

