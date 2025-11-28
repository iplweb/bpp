-- Recreate cache triggers for all 5 publication tables
CREATE TRIGGER bpp_wydawnictwo_ciagle_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_wydawnictwo_ciagle
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();

CREATE TRIGGER bpp_wydawnictwo_ciagle_autor_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_wydawnictwo_ciagle_autor
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();

CREATE TRIGGER bpp_wydawnictwo_zwarte_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_wydawnictwo_zwarte
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();

CREATE TRIGGER bpp_wydawnictwo_zwarte_autor_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_wydawnictwo_zwarte_autor
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();

CREATE TRIGGER bpp_patent_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_patent
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();

CREATE TRIGGER bpp_patent_autor_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_patent_autor
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();

CREATE TRIGGER bpp_praca_doktorska_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_praca_doktorska
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();

CREATE TRIGGER bpp_praca_habilitacyjna_cache_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_praca_habilitacyjna
  FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_cache();
