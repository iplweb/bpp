BEGIN;

DROP VIEW IF EXISTS bpp_wydawnictwo_ciagle_autorzy CASCADE;

CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_autorzy AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'wydawnictwo_ciagle'),
    rekord_id
    ] :: INTEGER [2] AS rekord_id,

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'wydawnictwo_ciagle'),
    id
    ] :: INTEGER [2] AS id,

    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako,
    zatrudniony,
    afiliuje,
    dyscyplina_naukowa_id,
    upowaznienie_pbn

  FROM bpp_wydawnictwo_ciagle_autor;


DROP VIEW IF EXISTS bpp_wydawnictwo_zwarte_autorzy CASCADE;

CREATE OR REPLACE VIEW bpp_wydawnictwo_zwarte_autorzy AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'wydawnictwo_zwarte'),
    rekord_id
    ] :: INTEGER [2] AS rekord_id,

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'wydawnictwo_zwarte'),
    id
    ] :: INTEGER [3] AS id,

    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako,
    zatrudniony,
    afiliuje,
    dyscyplina_naukowa_id,
    upowaznienie_pbn

  FROM bpp_wydawnictwo_zwarte_autor;


DROP VIEW IF EXISTS bpp_patent_autorzy CASCADE;

CREATE OR REPLACE VIEW bpp_patent_autorzy AS
  SELECT
    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'patent'),
    rekord_id
    ] :: INTEGER [2] AS rekord_id,

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'patent'),
    id
    ] :: INTEGER [2] AS id,

    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako,
    zatrudniony,
    afiliuje,
    dyscyplina_naukowa_id,
    upowaznienie_pbn

  FROM bpp_patent_autor;


DROP VIEW IF EXISTS bpp_praca_habilitacyjna_autorzy CASCADE;

CREATE OR REPLACE VIEW bpp_praca_habilitacyjna_autorzy AS
  SELECT

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'praca_habilitacyjna'),
    bpp_praca_habilitacyjna.id
    ] :: INTEGER [2]                              AS rekord_id,

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'praca_habilitacyjna'),
    bpp_praca_habilitacyjna.id
    ] :: INTEGER [2]                              AS id,

    autor_id,
    jednostka_id,
    1                                             AS kolejnosc,
    (
      SELECT id
      FROM bpp_typ_odpowiedzialnosci
      WHERE bpp_typ_odpowiedzialnosci.skrot = 'aut.'

    )                                             AS typ_odpowiedzialnosci_id,
    bpp_autor.nazwisko || ' ' || bpp_autor.imiona AS zapisany_jako,
    TRUE                                          AS zatrudniony,
    TRUE                                          AS afiliuje,
    NULL::INTEGER                                 AS dyscyplina_naukowa_id,
    FALSE                                         AS upowaznienie_pbn

  FROM
    bpp_praca_habilitacyjna, bpp_autor
  WHERE
    bpp_autor.id = bpp_praca_habilitacyjna.autor_id;


DROP VIEW IF EXISTS bpp_praca_doktorska_autorzy CASCADE;

CREATE OR REPLACE VIEW bpp_praca_doktorska_autorzy AS
  SELECT

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'praca_doktorska'),
    bpp_praca_doktorska.id
    ] :: INTEGER [2] AS rekord_id,

    ARRAY [
    (SELECT id
     FROM django_content_type
     WHERE
       django_content_type.app_label = 'bpp' AND
       django_content_type.model = 'praca_doktorska'),
    bpp_praca_doktorska.id
    ] :: INTEGER [2],

    autor_id,
    jednostka_id,
    1                AS kolejnosc,
    (
      SELECT id
      FROM bpp_typ_odpowiedzialnosci
      WHERE bpp_typ_odpowiedzialnosci.skrot = 'aut.'

    )                AS typ_odpowiedzialnosci_id,
    bpp_autor.nazwisko || ' ' ||
    bpp_autor.imiona AS zapisany_jako,
    TRUE             AS zatrudniony,
    TRUE             AS afiliuje,
    NULL::INTEGER                                 AS dyscyplina_naukowa_id,
    FALSE           AS upowaznienie_pbn

  FROM
    bpp_praca_doktorska, bpp_autor
  WHERE
    bpp_autor.id = bpp_praca_doktorska.autor_id;


DROP VIEW IF EXISTS bpp_autorzy;
CREATE VIEW bpp_autorzy AS
  SELECT *
  FROM bpp_wydawnictwo_ciagle_autorzy
  UNION ALL
  SELECT *
  FROM bpp_wydawnictwo_zwarte_autorzy
  UNION ALL
  SELECT *
  FROM bpp_patent_autorzy
  UNION ALL
  SELECT *
  FROM bpp_praca_doktorska_autorzy
  UNION ALL
  SELECT *
  FROM bpp_praca_habilitacyjna_autorzy;


DROP TABLE IF EXISTS bpp_autorzy_mat CASCADE;

CREATE TABLE bpp_autorzy_mat AS
  SELECT *
  FROM bpp_autorzy;

CREATE UNIQUE INDEX bpp_autorzy_mat_0
  ON bpp_autorzy_mat (id);

CREATE INDEX bpp_autorzy_mat_1
  ON bpp_autorzy_mat (rekord_id);

CREATE INDEX bpp_autorzy_mat_2
  ON bpp_autorzy_mat (autor_id);

CREATE INDEX bpp_autorzy_mat_3
  ON bpp_autorzy_mat (jednostka_id);

CREATE INDEX bpp_autorzy_mat_4
  ON bpp_autorzy_mat (autor_id, jednostka_id);

CREATE INDEX bpp_autorzy_mat_5
  ON bpp_autorzy_mat (autor_id, typ_odpowiedzialnosci_id);

CREATE INDEX bpp_autorzy_mat_6
  ON bpp_autorzy_mat (dyscyplina_naukowa_id);

CREATE INDEX bpp_autorzy_mat_7
  ON bpp_autorzy_mat (upowaznienie_pbn);

ALTER TABLE bpp_autorzy_mat
  ADD CONSTRAINT original_id_fk FOREIGN KEY (rekord_id) REFERENCES bpp_rekord_mat (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE bpp_autorzy_mat
  ADD CONSTRAINT jednostka_id_fk FOREIGN KEY (jednostka_id) REFERENCES bpp_jednostka (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE bpp_autorzy_mat
  ADD CONSTRAINT autor_id_fk FOREIGN KEY (autor_id) REFERENCES bpp_autor (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE bpp_autorzy_mat
  ADD CONSTRAINT typ_odpowiedzialnosci_id_fk FOREIGN KEY (typ_odpowiedzialnosci_id) REFERENCES bpp_typ_odpowiedzialnosci (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED; -- fore ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;

ALTER TABLE bpp_autorzy_mat
  ADD CONSTRAINT dyscyplina_naukowa_id_fk FOREIGN KEY (dyscyplina_naukowa_id) REFERENCES bpp_dyscyplina_naukowa(id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;


CREATE OR REPLACE RULE django_get_off_bpp_autorzy_view_1 AS ON DELETE TO bpp_autorzy DO INSTEAD NOTHING;

CREATE OR REPLACE RULE django_get_off_bpp_autorzy_view_2 AS ON UPDATE TO bpp_autorzy DO INSTEAD NOTHING;


COMMIT;
