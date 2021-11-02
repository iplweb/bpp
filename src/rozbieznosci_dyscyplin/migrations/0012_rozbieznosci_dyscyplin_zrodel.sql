BEGIN;

DROP VIEW IF EXISTS rozbieznosci_dyscyplin_rozbieznoscizrodelview;

CREATE VIEW rozbieznosci_dyscyplin_rozbieznoscizrodelview AS
SELECT DISTINCT  ARRAY [
         bpp_dyscyplina_zrodla.zrodlo_id,
         bpp_wydawnictwo_ciagle.id,
    bpp_wydawnictwo_ciagle_autor.autor_id,
    bpp_wydawnictwo_ciagle_autor.dyscyplina_naukowa_id] AS id,
                bpp_dyscyplina_zrodla.zrodlo_id,
                bpp_wydawnictwo_ciagle.id AS wydawnictwo_ciagle_id,
                bpp_wydawnictwo_ciagle_autor.autor_id,
                bpp_wydawnictwo_ciagle_autor.dyscyplina_naukowa_id
FROM bpp_wydawnictwo_ciagle_autor,
     bpp_dyscyplina_zrodla,
     bpp_wydawnictwo_ciagle
WHERE bpp_dyscyplina_zrodla.zrodlo_id = bpp_wydawnictwo_ciagle.zrodlo_id
  AND bpp_wydawnictwo_ciagle_autor.rekord_id = bpp_wydawnictwo_ciagle.id
  AND bpp_wydawnictwo_ciagle_autor.dyscyplina_naukowa_id NOT IN (
    SELECT dyscyplina_id
    FROM bpp_dyscyplina_zrodla
    WHERE bpp_dyscyplina_zrodla.zrodlo_id = bpp_wydawnictwo_ciagle.zrodlo_id);

COMMIT;
