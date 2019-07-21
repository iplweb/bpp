CREATE OR REPLACE VIEW rozbieznosci_dyscyplin_brakprzypisaniaview AS
SELECT ARRAY [
         bpp_rekord_mat.id[1],
         bpp_rekord_mat.id[2],
         bpp_autorzy_mat.autor_id]           AS id,
       bpp_rekord_mat.id                     AS rekord_id,
       bpp_rekord_mat.rok,
       bpp_autorzy_mat.autor_id,
       bpp_autorzy_mat.dyscyplina_naukowa_id AS dyscyplina_rekordu_id,
       NULL::integer                         AS dyscyplina_autora_id,
       NULL::integer                         AS subdyscyplina_autora_id
FROM bpp_rekord_mat,
     bpp_autorzy_mat
WHERE bpp_autorzy_mat.rekord_id = bpp_rekord_mat.id
  AND bpp_autorzy_mat.dyscyplina_naukowa_id IS NOT NULL
  AND NOT EXISTS(SELECT bpp_autor_dyscyplina.id
                 FROM bpp_autor_dyscyplina
                 WHERE rok = bpp_rekord_mat.rok
                   AND autor_id = bpp_autorzy_mat.autor_id);


CREATE OR REPLACE VIEW rozbieznosci_dyscyplin_rozbiezneprzypisaniaview AS
SELECT ARRAY [
         bpp_rekord_mat.id[1],
         bpp_rekord_mat.id[2],
         bpp_autorzy_mat.autor_id]                   AS id,
       bpp_rekord_mat.id                             AS rekord_id,
       bpp_rekord_mat.rok,
       bpp_autorzy_mat.autor_id,
       bpp_autorzy_mat.dyscyplina_naukowa_id         AS dyscyplina_rekordu_id,
       bpp_autor_dyscyplina.dyscyplina_naukowa_id    AS dyscyplina_autora_id,
       bpp_autor_dyscyplina.subdyscyplina_naukowa_id AS subdyscyplina_autora_id

FROM bpp_autorzy_mat,
     bpp_autor_dyscyplina,
     bpp_rekord_mat

WHERE bpp_rekord_mat.id = bpp_autorzy_mat.rekord_id
  AND ((
    bpp_rekord_mat.rok = bpp_autor_dyscyplina.rok
    AND bpp_autorzy_mat.autor_id = bpp_autor_dyscyplina.autor_id
    AND (
        bpp_autorzy_mat.dyscyplina_naukowa_id IS NULL
        OR bpp_autorzy_mat.dyscyplina_naukowa_id
          NOT IN (
                  bpp_autor_dyscyplina.dyscyplina_naukowa_id, bpp_autor_dyscyplina.subdyscyplina_naukowa_id)
      )
  ));


CREATE OR REPLACE VIEW rozbieznosci_dyscyplin_rozbieznosciview
AS SELECT *
   FROM rozbieznosci_dyscyplin_brakprzypisaniaview
   UNION ALL
   SELECT *
   FROM rozbieznosci_dyscyplin_rozbiezneprzypisaniaview;
