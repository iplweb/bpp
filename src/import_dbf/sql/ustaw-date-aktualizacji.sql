BEGIN;

UPDATE bpp_wydawnictwo_zwarte
SET ostatnio_zmieniony = TO_TIMESTAMP(import_dbf_bib.dat_akt, 'YYYYMMDDHH24MISS')
FROM import_dbf_bib
WHERE import_dbf_bib.content_type_id =
      (SELECT id FROM django_content_type WHERE app_label = 'bpp' AND model = 'wydawnictwo_zwarte')
  AND import_dbf_bib.object_id = bpp_wydawnictwo_zwarte.id;

UPDATE bpp_wydawnictwo_ciagle
SET ostatnio_zmieniony = TO_TIMESTAMP(import_dbf_bib.dat_akt, 'YYYYMMDDHH24MISS')
FROM import_dbf_bib
WHERE import_dbf_bib.content_type_id =
      (SELECT id FROM django_content_type WHERE app_label = 'bpp' AND model = 'wydawnictwo_ciagle')
  AND import_dbf_bib.object_id = bpp_wydawnictwo_ciagle.id;

COMMIT;
