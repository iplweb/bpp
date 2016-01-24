BEGIN;

DROP VIEW IF EXISTS bpp_wydawnictwo_ciagle_autorzy CASCADE;
CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_autorzy AS
  select
    django_content_type.id::text || '_' || rekord_id::text || '_' || autor_id::text || '_' || typ_odpowiedzialnosci_id::text || '_' || kolejnosc::text AS fake_id,

    django_content_type.id::text || '_' || rekord_id::text AS fake_rekord_id,

    django_content_type.id AS content_type_id,
    rekord_id as object_id,
    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako

  from bpp_wydawnictwo_ciagle_autor, django_content_type
  WHERE django_content_type.model = 'wydawnictwo_ciagle'
    AND django_content_type.app_label = 'bpp';

DROP VIEW IF EXISTS bpp_wydawnictwo_zwarte_autorzy CASCADE;
CREATE OR REPLACE VIEW bpp_wydawnictwo_zwarte_autorzy AS
  select
    django_content_type.id::text || '_' || rekord_id::text || '_' || autor_id::text || '_' || typ_odpowiedzialnosci_id::text || '_' || kolejnosc::text AS fake_id,

    django_content_type.id::text || '_' || rekord_id::text AS fake_rekord_id,

    django_content_type.id AS content_type_id,
    rekord_id as object_id,
    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako

  from bpp_wydawnictwo_zwarte_autor, django_content_type
  WHERE django_content_type.model = 'wydawnictwo_zwarte'
    AND django_content_type.app_label = 'bpp';

DROP VIEW IF EXISTS bpp_patent_autorzy CASCADE;
CREATE OR REPLACE VIEW bpp_patent_autorzy AS
  select
    django_content_type.id::text || '_' || rekord_id::text || '_' || autor_id::text || '_' || typ_odpowiedzialnosci_id::text || '_' || kolejnosc::text AS fake_id,

    django_content_type.id::text || '_' || rekord_id::text AS fake_rekord_id,

    django_content_type.id AS content_type_id,
    rekord_id as object_id,
    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako

  from bpp_patent_autor, django_content_type
  WHERE django_content_type.model = 'patent'
    AND django_content_type.app_label = 'bpp';

DROP VIEW IF EXISTS bpp_praca_habilitacyjna_autorzy CASCADE;
CREATE OR REPLACE VIEW bpp_praca_habilitacyjna_autorzy AS
  select
    django_content_type.id::text || '_' || bpp_praca_habilitacyjna.id || '_' || autor_id || '_' || bpp_typ_odpowiedzialnosci.id || '_' || 1::text AS fake_id,

    django_content_type.id::text || '_' || bpp_praca_habilitacyjna.id::text AS fake_rekord_id,

    django_content_type.id AS content_type_id,
    bpp_praca_habilitacyjna.id as object_id,
    autor_id,
    jednostka_id,
    1 AS kolejnosc,
    bpp_typ_odpowiedzialnosci.id AS typ_odpowiedzialnosci_id,
    bpp_autor.nazwisko || ' ' || bpp_autor.imiona AS zapisany_jako
  from
    bpp_praca_habilitacyjna, bpp_autor, bpp_typ_odpowiedzialnosci, django_content_type
  where
    bpp_autor.id = bpp_praca_habilitacyjna.autor_id AND
    bpp_typ_odpowiedzialnosci.skrot = 'aut.' AND
    django_content_type.model = 'praca_habilitacyjna' AND
    django_content_type.app_label = 'bpp';

DROP VIEW IF EXISTS bpp_praca_doktorska_autorzy CASCADE;
CREATE OR REPLACE VIEW bpp_praca_doktorska_autorzy AS
  select
    django_content_type.id::text || '_' || bpp_praca_doktorska.id || '_' || autor_id || '_' || bpp_typ_odpowiedzialnosci.id || '_' || 1::text AS fake_id,

    django_content_type.id::text || '_' || bpp_praca_doktorska.id::text AS fake_rekord_id,

    django_content_type.id AS content_type_id,
    bpp_praca_doktorska.id as object_id,
    autor_id,
    jednostka_id,
    1 AS kolejnosc,
    bpp_typ_odpowiedzialnosci.id AS typ_odpowiedzialnosci_id,
    bpp_autor.nazwisko || ' ' || bpp_autor.imiona AS zapisany_jako
  from
    bpp_praca_doktorska, bpp_autor, bpp_typ_odpowiedzialnosci, django_content_type
  where
    bpp_autor.id = bpp_praca_doktorska.autor_id AND
    bpp_typ_odpowiedzialnosci.skrot = 'aut.' AND
    django_content_type.model = 'praca_doktorska' AND
    django_content_type.app_label = 'bpp';


DROP VIEW IF EXISTS bpp_autorzy;
CREATE VIEW bpp_autorzy AS
  SELECT * FROM bpp_wydawnictwo_ciagle_autorzy
    UNION
      SELECT * FROM bpp_wydawnictwo_zwarte_autorzy
        UNION
          SELECT * FROM bpp_patent_autorzy
            UNION
              SELECT * FROM bpp_praca_doktorska_autorzy
                UNION
                  SELECT * FROM bpp_praca_habilitacyjna_autorzy;


COMMIT;
