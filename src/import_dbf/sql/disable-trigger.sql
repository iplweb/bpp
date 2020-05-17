BEGIN;

DROP TRIGGER IF EXISTS bpp_wydawnictwo_ciagle_cache_trigger ON bpp_wydawnictwo_ciagle;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_ciagle_autor_cache_trigger ON bpp_wydawnictwo_ciagle_autor;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_zwarte_cache_trigger ON bpp_wydawnictwo_zwarte;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_zwarte_autor_cache_trigger ON bpp_wydawnictwo_zwarte_autor;
DROP TRIGGER IF EXISTS bpp_praca_doktorska_cache_trigger ON bpp_praca_doktorska;
DROP TRIGGER IF EXISTS bpp_praca_habilitacyjna_cache_trigger ON bpp_praca_habilitacyjna;
DROP TRIGGER IF EXISTS bpp_patent_cache_trigger ON bpp_patent;
DROP TRIGGER IF EXISTS bpp_patent_autor_cache_trigger ON bpp_patent_autor;


DELETE FROM bpp_rekord_mat;
DELETE FROM bpp_autorzy_mat;

COMMIT;
