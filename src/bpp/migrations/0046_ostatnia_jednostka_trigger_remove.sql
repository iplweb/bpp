BEGIN;

DROP TRIGGER IF EXISTS bpp_autor_jednostka_ostatnia_jednostka_trigger ON bpp_autor_jednostka;

DROP FUNCTION bpp_autor_jednostka_ostatnia_jednostka;

COMMIT;
