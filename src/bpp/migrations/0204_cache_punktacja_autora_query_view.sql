BEGIN;

CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT bpp_cache_punktacja_autora.id,
       bpp_cache_punktacja_autora.rekord_id,
       bpp_cache_punktacja_autora.pkdaut,
       bpp_cache_punktacja_autora.slot,
       bpp_cache_punktacja_autora.autor_id,
       bpp_cache_punktacja_autora.dyscyplina_id,
       bpp_cache_punktacja_autora.jednostka_id,
       bpp_cache_punktacja_dyscypliny.autorzy_z_dyscypliny,
       bpp_cache_punktacja_dyscypliny.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora,
     bpp_cache_punktacja_dyscypliny
WHERE bpp_cache_punktacja_autora.rekord_id = bpp_cache_punktacja_dyscypliny.rekord_id
  AND bpp_cache_punktacja_autora.dyscyplina_id = bpp_cache_punktacja_dyscypliny.dyscyplina_id;


COMMIT;
