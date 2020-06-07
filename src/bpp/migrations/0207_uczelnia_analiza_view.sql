BEGIN;

DROP VIEW IF EXISTS bpp_uczelnia_ewaluacja_view;

CREATE VIEW bpp_uczelnia_ewaluacja_view AS

SELECT ARRAY [bpp_rekord_mat.id[1],
           bpp_rekord_mat.id[2],
           bpp_autorzy_mat.autor_id, bpp_autorzy_mat.kolejnosc]:: INTEGER[4] AS id,

       bpp_rekord_mat.id                                                     AS rekord_id,
       bpp_autorzy_mat.id                                                    as autorzy_id,
       bpp_autor_dyscyplina.id                                               AS autor_dyscyplina_id,

       bpp_cache_punktacja_dyscypliny.autorzy_z_dyscypliny,
       bpp_cache_punktacja_autora.pkdaut,
       bpp_cache_punktacja_autora.slot

FROM bpp_rekord_mat

         INNER JOIN bpp_autorzy_mat ON bpp_rekord_mat.id = bpp_autorzy_mat.rekord_id

         INNER JOIN bpp_cache_punktacja_dyscypliny
                    ON bpp_cache_punktacja_dyscypliny.dyscyplina_id = bpp_autorzy_mat.dyscyplina_naukowa_id AND
                       bpp_cache_punktacja_dyscypliny.rekord_id = bpp_autorzy_mat.rekord_id

         INNER JOIN bpp_cache_punktacja_autora ON bpp_cache_punktacja_autora.rekord_id = bpp_autorzy_mat.rekord_id AND
                                                  bpp_cache_punktacja_autora.autor_id = bpp_autorzy_mat.autor_id

         INNER JOIN bpp_autor_dyscyplina ON bpp_autor_dyscyplina.autor_id = bpp_autorzy_mat.autor_id AND
                                            bpp_autor_dyscyplina.rok = bpp_rekord_mat.rok;


CREATE INDEX IF NOT EXISTS bpp_cache_punktacja_autora_rekord_autor_idx ON bpp_cache_punktacja_autora (rekord_id, autor_id);
CREATE INDEX IF NOT EXISTS bpp_autor_dyscyplina_autor_rok_idx ON bpp_autor_dyscyplina (autor_id, rok);

COMMIT;
