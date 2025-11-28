BEGIN;

-- Drop bpp_refresh_cache triggers (all 5 publication tables + 3 autor tables)
DROP TRIGGER IF EXISTS bpp_wydawnictwo_ciagle_cache_trigger ON bpp_wydawnictwo_ciagle;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_ciagle_autor_cache_trigger ON bpp_wydawnictwo_ciagle_autor;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_zwarte_cache_trigger ON bpp_wydawnictwo_zwarte;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_zwarte_autor_cache_trigger ON bpp_wydawnictwo_zwarte_autor;
DROP TRIGGER IF EXISTS bpp_patent_cache_trigger ON bpp_patent;
DROP TRIGGER IF EXISTS bpp_patent_autor_cache_trigger ON bpp_patent_autor;
DROP TRIGGER IF EXISTS bpp_praca_doktorska_cache_trigger ON bpp_praca_doktorska;
DROP TRIGGER IF EXISTS bpp_praca_habilitacyjna_cache_trigger ON bpp_praca_habilitacyjna;

-- Drop materialized tables (bpp_autorzy_mat first due to FK constraint to bpp_rekord_mat)
DROP TABLE IF EXISTS bpp_autorzy_mat CASCADE;
DROP TABLE IF EXISTS bpp_rekord_mat CASCADE;

COMMIT;
