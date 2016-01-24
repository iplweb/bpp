BEGIN;

-- strip tags function
-- we use this to strip all html tags but still preserving the href
-- attribute value so tsearch later can match host.
-- Does two runs:
-- 1) strip all tags containg the attribute href but preserve the
--    attribute value and put it in parentheses.
-- 2) strip of any remaining tags
CREATE OR REPLACE FUNCTION strip_tags(TEXT) RETURNS TEXT AS $$
    SELECT regexp_replace(
        regexp_replace($1,
           E'<[^>]*?(\s* href \s* = \s* ([\'"]) ([^>]*?) ([\'"]) ) [^>]*?>',
           E' (\\3) ',
            'gx'),
        E'(< [^>]*? >)',
        E'',
         'gx')
$$ LANGUAGE SQL;



CREATE EXTENSION IF NOT EXISTS unaccent;

DROP TEXT SEARCH CONFIGURATION IF EXISTS bpp_nazwy_wlasne ;

CREATE TEXT SEARCH CONFIGURATION bpp_nazwy_wlasne ( COPY = english );

ALTER TEXT SEARCH CONFIGURATION bpp_nazwy_wlasne
  ALTER MAPPING FOR asciiword, asciihword, hword_asciipart, word, hword, hword_part
  WITH unaccent, simple;

CREATE OR REPLACE FUNCTION ts_post_bpp_autor_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN
    v :=
      COALESCE(NEW.nazwisko, '') || ' ' ||
      COALESCE(NEW.imiona, '') || ' ' ||
      COALESCE(NEW.poprzednie_nazwiska, '');

    NEW.search := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_autor_search ON bpp_autor;

CREATE TRIGGER ts_post_bpp_autor_search
  BEFORE INSERT OR UPDATE ON bpp_autor
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_autor_search();




CREATE OR REPLACE FUNCTION ts_post_bpp_jednostka_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN

    IF NEW.widoczna = FALSE THEN
      NEW.search := NULL;
      RETURN NEW;
    END IF;

    v :=
      COALESCE(NEW.nazwa, '') || ' ' ||
      COALESCE(NEW.opis, '');

    NEW.search := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_jednostka_search ON bpp_jednostka;

CREATE TRIGGER ts_post_bpp_jednostka_search
  BEFORE INSERT OR UPDATE ON bpp_jednostka
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_jednostka_search();




CREATE OR REPLACE FUNCTION ts_post_bpp_zrodlo_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN

    v :=
      COALESCE(NEW.nazwa, '') || ' ' ||
      COALESCE(NEW.poprzednia_nazwa, '') || ' ' ||
      COALESCE(NEw.skrot, '');

    NEW.search := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_zrodlo_search ON bpp_zrodlo;

CREATE TRIGGER ts_post_bpp_zrodlo_search
  BEFORE INSERT OR UPDATE ON bpp_zrodlo
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_zrodlo_search();







CREATE OR REPLACE FUNCTION ts_post_bpp_wydawnictwo_ciagle_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN

    v :=
      strip_tags(
          COALESCE(NEW.tytul_oryginalny, '') || ' ' ||
          COALESCE(NEW.tytul, ''));

    NEW.search_index := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_wydawnictwo_ciagle_search ON bpp_wydawnictwo_ciagle;

CREATE TRIGGER ts_post_bpp_wydawnictwo_ciagle_search
  BEFORE INSERT OR UPDATE ON bpp_wydawnictwo_ciagle
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_wydawnictwo_ciagle_search();








CREATE OR REPLACE FUNCTION ts_post_bpp_wydawnictwo_zwarte_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN

    v :=
      strip_tags(
          COALESCE(NEW.tytul_oryginalny, '') || ' ' ||
          COALESCE(NEW.tytul, ''));

    NEW.search_index := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_wydawnictwo_zwarte_search ON bpp_wydawnictwo_zwarte;

CREATE TRIGGER ts_post_bpp_wydawnictwo_zwarte_search
  BEFORE INSERT OR UPDATE ON bpp_wydawnictwo_zwarte
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_wydawnictwo_zwarte_search();







CREATE OR REPLACE FUNCTION ts_post_bpp_praca_doktorska_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN

    v :=
      strip_tags(
          COALESCE(NEW.tytul_oryginalny, '') || ' ' ||
          COALESCE(NEW.tytul, ''));

    NEW.search_index := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_praca_doktorska_search ON bpp_praca_doktorska;

CREATE TRIGGER ts_post_bpp_praca_doktorska_search
  BEFORE INSERT OR UPDATE ON bpp_praca_doktorska
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_praca_doktorska_search();





CREATE OR REPLACE FUNCTION ts_post_bpp_praca_habilitacyjna_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN

    v :=
      strip_tags(
          COALESCE(NEW.tytul_oryginalny, '') || ' ' ||
          COALESCE(NEW.tytul, ''));

    NEW.search_index := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_praca_habilitacyjna_search ON bpp_praca_habilitacyjna;

CREATE TRIGGER ts_post_bpp_praca_habilitacyjna_search
  BEFORE INSERT OR UPDATE ON bpp_praca_habilitacyjna
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_praca_habilitacyjna_search();



CREATE OR REPLACE FUNCTION ts_post_bpp_patent_search() RETURNS trigger AS $$
  DECLARE
    v TEXT;

  BEGIN

    v :=
      strip_tags(
          COALESCE(NEW.tytul_oryginalny, '')
          );

    NEW.search_index := to_tsvector('bpp_nazwy_wlasne', v);

    RETURN NEW;
  END;

  $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ts_post_bpp_patent_search ON bpp_patent;

CREATE TRIGGER ts_post_bpp_patent_search
  BEFORE INSERT OR UPDATE ON bpp_patent
  FOR EACH ROW EXECUTE PROCEDURE ts_post_bpp_patent_search();




UPDATE bpp_autor SET id=id;

UPDATE bpp_zrodlo SET id=id;

UPDATE bpp_jednostka SET id=id;

UPDATE bpp_wydawnictwo_ciagle SET id=id;

UPDATE bpp_wydawnictwo_zwarte SET id=id;

UPDATE bpp_patent SET id=id;

UPDATE bpp_praca_doktorska SET id=id;

UPDATE bpp_praca_habilitacyjna SET id=id;


COMMIT;