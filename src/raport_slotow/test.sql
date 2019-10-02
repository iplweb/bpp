CREATE TEMPORARY TABLE "bpp_temporary_cpaq" AS
SELECT "bpp_cache_punktacja_autora"."id",
       "bpp_cache_punktacja_autora"."autor_id",
       "bpp_cache_punktacja_autora"."dyscyplina_id",
       "bpp_cache_punktacja_autora"."pkdaut",
       "bpp_cache_punktacja_autora"."slot",
       "bpp_cache_punktacja_autora"."rekord_id",
       ("bpp_cache_punktacja_autora"."pkdaut" / "bpp_cache_punktacja_autora"."slot")              AS "pkdautslot",
       SUM("bpp_cache_punktacja_autora"."slot")
       OVER (PARTITION BY "bpp_cache_punktacja_autora"."autor_id", "bpp_cache_punktacja_autora"."dyscyplina_id" ORDER BY (
               "bpp_cache_punktacja_autora"."pkdaut" / "bpp_cache_punktacja_autora"."slot") DESC) AS "pkdautslotsum"
FROM "bpp_cache_punktacja_autora"
         INNER JOIN "bpp_rekord_mat" ON ("bpp_cache_punktacja_autora"."rekord_id" = "bpp_rekord_mat"."id")
         INNER JOIN "bpp_autor" ON ("bpp_cache_punktacja_autora"."autor_id" = "bpp_autor"."id")
WHERE ("bpp_cache_punktacja_autora"."pkdaut" > % s AND "bpp_rekord_mat"."rok" = % s)
ORDER BY "bpp_autor"."sort" ASC, ("bpp_cache_punktacja_autora"."pkdaut" / "bpp_cache_punktacja_autora"."slot") DESC
