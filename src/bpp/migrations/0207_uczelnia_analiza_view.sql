BEGIN;

DROP VIEW IF EXISTS bpp_uczelnia_ewaluacja_view;

CREATE VIEW bpp_uczelnia_ewaluacja_view AS

SELECT ARRAY [bpp_rekord_mat.id[0],
           bpp_rekord_mat.id[1],
           bpp_autorzy_mat.autor_id, bpp_autorzy_mat.kolejnosc]:: INTEGER[4] AS id,

       bpp_rekord_mat.id                                                     AS rekord_id,
       bpp_autorzy_mat.id as autorzy_id,
       bpp_autor_dyscyplina.id AS autor_dyscyplina_id,

       bpp_cache_punktacja_dyscypliny.autorzy_z_dyscypliny,
       bpp_cache_punktacja_autora.pkdaut,
       bpp_cache_punktacja_autora.slot

FROM bpp_rekord_mat,
     bpp_cache_punktacja_dyscypliny,
     bpp_cache_punktacja_autora,
     bpp_autorzy_mat,
     bpp_autor_dyscyplina

WHERE bpp_rekord_mat.id = bpp_autorzy_mat.rekord_id
  AND bpp_cache_punktacja_dyscypliny.dyscyplina_id = bpp_autorzy_mat.dyscyplina_naukowa_id
  AND bpp_cache_punktacja_dyscypliny.rekord_id = bpp_rekord_mat.id
  AND bpp_cache_punktacja_dyscypliny.rekord_id = bpp_autorzy_mat.rekord_id
  AND bpp_cache_punktacja_autora.rekord_id = bpp_autorzy_mat.rekord_id
  AND bpp_cache_punktacja_autora.rekord_id = bpp_cache_punktacja_dyscypliny.rekord_id
  AND bpp_cache_punktacja_autora.autor_id = bpp_autorzy_mat.autor_id
  AND bpp_autor_dyscyplina.autor_id = bpp_autorzy_mat.autor_id
  AND bpp_autor_dyscyplina.rok = bpp_rekord_mat.rok;


COMMIT;
