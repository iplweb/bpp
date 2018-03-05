BEGIN;


DROP VIEW IF EXISTS bpp_wydawnictwo_ciagle_view CASCADE;

CREATE VIEW bpp_wydawnictwo_ciagle_view AS
  SELECT

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'wydawnictwo_ciagle'),
    bpp_wydawnictwo_ciagle.id
    ] :: INTEGER [2] AS id,

    tytul_oryginalny,
    tytul,
    search_index,

    rok,

    jezyk_id,
    typ_kbn_id,

    charakter_formalny_id,

    zrodlo_id,

    NULL :: TEXT     AS wydawnictwo,

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
    ostatnio_zmieniony_dla_pbn,

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
    bpp_wydawnictwo_ciagle;


DROP VIEW IF EXISTS bpp_wydawnictwo_zwarte_view CASCADE;


CREATE VIEW bpp_wydawnictwo_zwarte_view AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'wydawnictwo_zwarte'),
    bpp_wydawnictwo_zwarte.id
    ] :: INTEGER [2] AS id,


    tytul_oryginalny,
    tytul,
    search_index,

    rok,

    jezyk_id,
    typ_kbn_id,

    charakter_formalny_id,

    NULL :: INTEGER  AS zrodlo_id,

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
    ostatnio_zmieniony_dla_pbn,

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
    bpp_wydawnictwo_zwarte;


DROP VIEW IF EXISTS bpp_patent_view CASCADE;

CREATE VIEW bpp_patent_view AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'patent'),
    bpp_patent.id
    ] :: INTEGER [2]                             AS id,


    tytul_oryginalny,
    NULL :: TEXT                                 AS tytul,
    search_index,

    rok,

    (SELECT id
     FROM bpp_jezyk
     WHERE bpp_jezyk.skrot = 'pol.')             AS jezyk_id,

    (SELECT id
     FROM bpp_typ_kbn
     WHERE bpp_typ_kbn.skrot = 'PO')             AS typ_kbn_id,

    (SELECT id
     FROM bpp_charakter_formalny
     WHERE bpp_charakter_formalny.skrot = 'PAT') AS charakter_formalny_id,

    NULL :: INTEGER                              AS zrodlo_id,

    NULL :: TEXT                                 AS wydawnictwo,

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
    NULL :: DATE                                AS ostatnio_zmieniony_dla_pbn,

    tytul_oryginalny_sort,
    opis_bibliograficzny_cache,
    opis_bibliograficzny_autorzy_cache,
    opis_bibliograficzny_zapisani_autorzy_cache,

    recenzowana,

    '0' :: INTEGER                               AS liczba_znakow_wydawniczych,

    www,

    NULL :: INTEGER                              AS openaccess_czas_publikacji_id,
    NULL :: INTEGER                              AS openaccess_licencja_id,
    NULL :: INTEGER                              AS openaccess_tryb_dostepu_id,
    NULL :: INTEGER                              AS openaccess_wersja_tekstu_id,
    NULL :: INTEGER                              AS openaccess_ilosc_miesiecy,

    NULL :: INTEGER                              AS konferencja_id

  FROM
    bpp_patent;


DROP VIEW IF EXISTS bpp_praca_doktorska_view CASCADE;

CREATE VIEW bpp_praca_doktorska_view AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'praca_doktorska'),
    bpp_praca_doktorska.id
    ] :: INTEGER [2]                           AS id,

    tytul_oryginalny,
    tytul,
    search_index,

    rok,

    jezyk_id,
    typ_kbn_id,

    (SELECT id
     FROM bpp_charakter_formalny
     WHERE bpp_charakter_formalny.skrot = 'D') AS charakter_formalny_id,

    NULL :: INTEGER                            AS zrodlo_id,

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
    NULL :: DATE                                AS ostatnio_zmieniony_dla_pbn,

    tytul_oryginalny_sort,
    opis_bibliograficzny_cache,
    opis_bibliograficzny_autorzy_cache,
    opis_bibliograficzny_zapisani_autorzy_cache,

    recenzowana,

    '0' :: INTEGER                             AS liczba_znakow_wydawniczych,

    www,

    NULL :: INTEGER                            AS openaccess_czas_publikacji_id,
    NULL :: INTEGER                            AS openaccess_licencja_id,
    NULL :: INTEGER                            AS openaccess_tryb_dostepu_id,
    NULL :: INTEGER                            AS openaccess_wersja_tekstu_id,
    NULL :: INTEGER                            AS openaccess_ilosc_miesiecy,

    NULL :: INTEGER                            AS konferencja_id


  FROM
    bpp_praca_doktorska;


DROP VIEW IF EXISTS bpp_praca_habilitacyjna_view CASCADE;

CREATE VIEW bpp_praca_habilitacyjna_view AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'praca_habilitacyjna'),
    bpp_praca_habilitacyjna.id
    ] :: INTEGER [2]                           AS id,

    tytul_oryginalny,
    tytul,
    search_index,

    rok,

    jezyk_id,
    typ_kbn_id,

    (SELECT id
     FROM bpp_charakter_formalny
     WHERE bpp_charakter_formalny.skrot = 'H') AS charakter_formalny_id,

    NULL :: INTEGER                            AS zrodlo_id,

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
    NULL :: DATE                                AS ostatnio_zmieniony_dla_pbn,

    tytul_oryginalny_sort,
    opis_bibliograficzny_cache,
    opis_bibliograficzny_autorzy_cache,
    opis_bibliograficzny_zapisani_autorzy_cache,

    recenzowana,

    '0' :: INTEGER                             AS liczba_znakow_wydawniczych,

    www,

    NULL :: INTEGER                            AS openaccess_czas_publikacji_id,
    NULL :: INTEGER                            AS openaccess_licencja_id,
    NULL :: INTEGER                            AS openaccess_tryb_dostepu_id,
    NULL :: INTEGER                            AS openaccess_wersja_tekstu_id,
    NULL :: INTEGER                            AS openaccess_ilosc_miesiecy,

    NULL :: INTEGER                            AS konferencja_id


  FROM
    bpp_praca_habilitacyjna;


DROP VIEW IF EXISTS bpp_rekord CASCADE;

CREATE VIEW bpp_rekord AS
  SELECT *
  FROM bpp_wydawnictwo_ciagle_view
  UNION ALL
  SELECT *
  FROM bpp_wydawnictwo_zwarte_view
  UNION ALL
  SELECT *
  FROM bpp_patent_view
  UNION ALL
  SELECT *
  FROM bpp_praca_doktorska_view
  UNION ALL
  SELECT *
  FROM bpp_praca_habilitacyjna_view;


DROP TABLE IF EXISTS bpp_rekord_mat CASCADE;

CREATE TABLE bpp_rekord_mat AS
  SELECT *
  FROM bpp_rekord;


CREATE UNIQUE INDEX bpp_rekord_mat_fake_id_idx
  ON bpp_rekord_mat (id);

CREATE INDEX bpp_rekord_mat_tytul_oryginalny_idx
  ON bpp_rekord_mat (tytul_oryginalny);
CREATE INDEX bpp_rekord_mat_search_index_idx
  ON bpp_rekord_mat USING GIST (search_index);
CREATE INDEX bpp_rekord_mat_1
  ON bpp_rekord_mat (jezyk_id);
CREATE INDEX bpp_rekord_mat_2
  ON bpp_rekord_mat (typ_kbn_id);
CREATE INDEX bpp_rekord_mat_3
  ON bpp_rekord_mat (charakter_formalny_id);
CREATE INDEX bpp_rekord_mat_4
  ON bpp_rekord_mat (zrodlo_id);
CREATE INDEX bpp_rekord_mat_5
  ON bpp_rekord_mat (wydawnictwo);
CREATE INDEX bpp_rekord_mat_6
  ON bpp_rekord_mat (slowa_kluczowe);
CREATE INDEX bpp_rekord_mat_7
  ON bpp_rekord_mat (impact_factor);
CREATE INDEX bpp_rekord_mat_8
  ON bpp_rekord_mat (punkty_kbn);
CREATE INDEX bpp_rekord_mat_9
  ON bpp_rekord_mat (index_copernicus);
CREATE INDEX bpp_rekord_mat_a
  ON bpp_rekord_mat (punktacja_wewnetrzna);
CREATE INDEX bpp_rekord_mat_b
  ON bpp_rekord_mat (kc_impact_factor);
CREATE INDEX bpp_rekord_mat_c
  ON bpp_rekord_mat (kc_punkty_kbn);
CREATE INDEX bpp_rekord_mat_d
  ON bpp_rekord_mat (kc_index_copernicus);
CREATE INDEX bpp_rekord_mat_e
  ON bpp_rekord_mat (uwagi);
CREATE INDEX bpp_rekord_mat_f
  ON bpp_rekord_mat (adnotacje);
CREATE INDEX bpp_rekord_mat_g
  ON bpp_rekord_mat (utworzono);
CREATE INDEX bpp_rekord_mat_h
  ON bpp_rekord_mat (ostatnio_zmieniony);
CREATE INDEX bpp_rekord_mat_i
  ON bpp_rekord_mat (rok);
CREATE INDEX bpp_rekord_mat_k
  ON bpp_rekord_mat (recenzowana);
CREATE INDEX bpp_rekord_mat_l
  ON bpp_rekord_mat (openaccess_czas_publikacji_id);
CREATE INDEX bpp_rekord_mat_m
  ON bpp_rekord_mat (openaccess_licencja_id);
CREATE INDEX bpp_rekord_mat_n
  ON bpp_rekord_mat (openaccess_tryb_dostepu_id);
CREATE INDEX bpp_rekord_mat_o
  ON bpp_rekord_mat (openaccess_wersja_tekstu_id);

ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT zrodlo_id_fk FOREIGN KEY (zrodlo_id) REFERENCES bpp_zrodlo (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT charakter_formalny_id_fk FOREIGN KEY (charakter_formalny_id) REFERENCES bpp_charakter_formalny (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT jezyk_id_fk FOREIGN KEY (jezyk_id) REFERENCES bpp_jezyk (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE bpp_rekord_mat
  ADD CONSTRAINT typ_kbn_id_fk FOREIGN KEY (typ_kbn_id) REFERENCES bpp_typ_kbn (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED;


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

CREATE OR REPLACE RULE django_get_off_bpp_rekord_view_1 AS ON DELETE TO bpp_rekord DO INSTEAD NOTHING;
CREATE OR REPLACE RULE django_get_off_bpp_rekord_view_2 AS ON UPDATE TO bpp_rekord DO INSTEAD NOTHING;

COMMIT;

