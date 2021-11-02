BEGIN;

DROP VIEW IF EXISTS bpp_ewaluacja_upowaznienia_view;


CREATE VIEW bpp_ewaluacja_upowaznienia_view AS

SELECT ARRAY [bpp_rekord_mat.id[1],
           bpp_rekord_mat.id[2],
           bpp_autorzy_mat.autor_id, bpp_autorzy_mat.kolejnosc]:: INTEGER[4] AS id,

       bpp_rekord_mat.id                                                     AS rekord_id,
       bpp_autorzy_mat.id                                                    as autorzy_id,
       bpp_autor_dyscyplina.id                                               AS autor_dyscyplina_id


FROM bpp_rekord_mat

         INNER JOIN bpp_autorzy_mat ON bpp_rekord_mat.id = bpp_autorzy_mat.rekord_id

         INNER JOIN bpp_autor_dyscyplina ON bpp_autor_dyscyplina.autor_id = bpp_autorzy_mat.autor_id AND
                                            bpp_autor_dyscyplina.rok = bpp_rekord_mat.rok


WHERE bpp_rekord_mat.punkty_kbn > 0
  AND bpp_autorzy_mat.dyscyplina_naukowa_id IS NOT NULL
  AND bpp_autorzy_mat.afiliuje = 'false';



COMMIT;
