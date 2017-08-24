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

  recenzowana,

  liczba_znakow_wydawniczych,

  www,

  openaccess_czas_publikacji_id,
  openaccess_licencja_id,
  openaccess_tryb_dostepu_id,
  openaccess_wersja_tekstu_id,
  openaccess_ilosc_miesiecy,

  konferencja_id

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

  recenzowana,

  liczba_znakow_wydawniczych,

  www,

  openaccess_czas_publikacji_id,
  openaccess_licencja_id,
  openaccess_tryb_dostepu_id,
  openaccess_wersja_tekstu_id,
  openaccess_ilosc_miesiecy,

  konferencja_id


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

  recenzowana,

  '0'::integer AS liczba_znakow_wydawniczych,

  www,

  NULL::integer AS openaccess_czas_publikacji_id,
  NULL::integer AS openaccess_licencja_id,
  NULL::integer AS openaccess_tryb_dostepu_id,
  NULL::integer AS openaccess_wersja_tekstu_id,
  NULL::integer AS openaccess_ilosc_miesiecy,

  NULL::integer AS konferencja_id


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

  recenzowana,

  '0'::integer AS liczba_znakow_wydawniczych,

  www,

  NULL::integer AS openaccess_czas_publikacji_id,
  NULL::integer AS openaccess_licencja_id,
  NULL::integer AS openaccess_tryb_dostepu_id,
  NULL::integer AS openaccess_wersja_tekstu_id,
  NULL::integer AS openaccess_ilosc_miesiecy,

  NULL::integer AS konferencja_id


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

  recenzowana,

  '0'::integer AS liczba_znakow_wydawniczych,

  www,

  NULL::integer AS openaccess_czas_publikacji_id,
  NULL::integer AS openaccess_licencja_id,
  NULL::integer AS openaccess_tryb_dostepu_id,
  NULL::integer AS openaccess_wersja_tekstu_id,
  NULL::integer AS openaccess_ilosc_miesiecy,

  NULL::integer AS konferencja_id


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



DROP TABLE IF EXISTS bpp_rekord_mat CASCADE;

CREATE TABLE bpp_rekord_mat AS SELECT * FROM bpp_rekord;


CREATE UNIQUE INDEX bpp_rekord_mat_fake_id_idx ON bpp_rekord_mat(fake_id);
CREATE UNIQUE INDEX bpp_rekord_mat_original_idx ON bpp_rekord_mat(content_type_id, object_id);

CREATE INDEX bpp_rekord_mat_tytul_oryginalny_idx ON bpp_rekord_mat(tytul_oryginalny);
CREATE INDEX bpp_rekord_mat_search_index_idx ON bpp_rekord_mat USING GIST(search_index);
CREATE INDEX bpp_rekord_mat_1 ON bpp_rekord_mat(jezyk_id);
CREATE INDEX bpp_rekord_mat_2 ON bpp_rekord_mat(typ_kbn_id);
CREATE INDEX bpp_rekord_mat_3 ON bpp_rekord_mat(charakter_formalny_id);
CREATE INDEX bpp_rekord_mat_4 ON bpp_rekord_mat(zrodlo_id);
CREATE INDEX bpp_rekord_mat_5 ON bpp_rekord_mat(wydawnictwo);
CREATE INDEX bpp_rekord_mat_6 ON bpp_rekord_mat(slowa_kluczowe);
CREATE INDEX bpp_rekord_mat_7 ON bpp_rekord_mat(impact_factor);
CREATE INDEX bpp_rekord_mat_8 ON bpp_rekord_mat(punkty_kbn);
CREATE INDEX bpp_rekord_mat_9 ON bpp_rekord_mat(index_copernicus);
CREATE INDEX bpp_rekord_mat_a ON bpp_rekord_mat(punktacja_wewnetrzna);
CREATE INDEX bpp_rekord_mat_b ON bpp_rekord_mat(kc_impact_factor);
CREATE INDEX bpp_rekord_mat_c ON bpp_rekord_mat(kc_punkty_kbn);
CREATE INDEX bpp_rekord_mat_d ON bpp_rekord_mat(kc_index_copernicus);
CREATE INDEX bpp_rekord_mat_e ON bpp_rekord_mat(uwagi);
CREATE INDEX bpp_rekord_mat_f ON bpp_rekord_mat(adnotacje);
CREATE INDEX bpp_rekord_mat_g ON bpp_rekord_mat(utworzono);
CREATE INDEX bpp_rekord_mat_h ON bpp_rekord_mat(ostatnio_zmieniony);
CREATE INDEX bpp_rekord_mat_i ON bpp_rekord_mat(rok);
CREATE INDEX bpp_rekord_mat_k ON bpp_rekord_mat(recenzowana);
CREATE INDEX bpp_rekord_mat_l ON bpp_rekord_mat(openaccess_czas_publikacji_id);
CREATE INDEX bpp_rekord_mat_m ON bpp_rekord_mat(openaccess_licencja_id);
CREATE INDEX bpp_rekord_mat_n ON bpp_rekord_mat(openaccess_tryb_dostepu_id);
CREATE INDEX bpp_rekord_mat_o ON bpp_rekord_mat(openaccess_wersja_tekstu_id);

ALTER TABLE bpp_rekord_mat ADD CONSTRAINT zrodlo_id_fk FOREIGN KEY (zrodlo_id) REFERENCES bpp_zrodlo (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_rekord_mat ADD CONSTRAINT charakter_formalny_id_fk FOREIGN KEY (charakter_formalny_id) REFERENCES bpp_charakter_formalny (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_rekord_mat ADD CONSTRAINT jezyk_id_fk FOREIGN KEY (jezyk_id) REFERENCES bpp_jezyk (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_rekord_mat ADD CONSTRAINT typ_kbn_id_fk FOREIGN KEY (typ_kbn_id) REFERENCES bpp_typ_kbn (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;

ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT content_type_fk
FOREIGN KEY (content_type_id)
REFERENCES django_content_type(id)
ON DELETE CASCADE
ON UPDATE CASCADE
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT openaccess_wersja_tekstu_fk
FOREIGN KEY (openaccess_wersja_tekstu_id)
REFERENCES bpp_wersja_tekstu_openaccess (id)
ON DELETE CASCADE
ON UPDATE CASCADE
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT openaccess_licencja_fk
FOREIGN KEY (openaccess_licencja_id)
REFERENCES bpp_licencja_openaccess (id)
ON DELETE CASCADE
ON UPDATE CASCADE
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT openaccess_czas_publikacji_fk
FOREIGN KEY (openaccess_czas_publikacji_id)
REFERENCES bpp_czas_udostepnienia_openaccess (id)
ON DELETE CASCADE
ON UPDATE CASCADE
DEFERRABLE INITIALLY DEFERRED;


ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT konferencja_id_fk
FOREIGN KEY (konferencja_id)
REFERENCES bpp_konferencja(id)
ON DELETE CASCADE
ON UPDATE CASCADE
DEFERRABLE INITIALLY DEFERRED;


COMMIT;

