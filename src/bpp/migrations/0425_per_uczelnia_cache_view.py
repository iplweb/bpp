from django.db import migrations

DROP = "DROP VIEW IF EXISTS bpp_cache_punktacja_autora_view;"

CREATE_NEW = """
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT a.id,
       a.rekord_id,
       a.pkdaut,
       a.slot,
       a.autor_id,
       a.dyscyplina_id,
       a.jednostka_id,
       d.autorzy_z_dyscypliny,
       d.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora a
JOIN bpp_jednostka j ON j.id = a.jednostka_id
JOIN bpp_cache_punktacja_dyscypliny d
  ON a.rekord_id = d.rekord_id
 AND a.dyscyplina_id = d.dyscyplina_id
 AND d.uczelnia_id = j.uczelnia_id;
"""

CREATE_OLD = """
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
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0424_cache_punktacja_dyscypliny_uczelnia_and_more"),
    ]

    operations = [
        migrations.RunSQL(sql=DROP + CREATE_NEW, reverse_sql=DROP + CREATE_OLD),
    ]
