from django.db import migrations


class Migration(migrations.Migration):
    # CONCURRENTLY nie może działać w bloku transakcji — stąd atomic=False
    # oraz osobne operacje RunSQL (kilka statementów w jednym stringu
    # psycopg wykonuje w niejawnej transakcji).
    atomic = False

    dependencies = [
        ("bpp", "0430_rekord_mat_slug_idx"),
    ]

    operations = [
        # GiST -> GIN dla indeksu pełnotekstowego. Benchmark na zrzucie
        # produkcyjnym (122k rekordów, 2026-06, kształty zapytań BPP):
        #   prefix :*        47.6 ->  12.6 ms  (3.8x)
        #   AND 2 termów     47.4 ->   2.4 ms  (19.6x)
        #   websearch        14.7 ->   8.9 ms  (1.7x)
        #   ranking top-20   48.7 ->  13.2 ms  (3.7x)
        # zapis (UPDATE 1000 publ. przez trigger): bez regresji;
        # rozmiar 15 vs 11 MB; budowa 0.4 s. GIN jest też wariantem
        # rekomendowanym dla tsvector w dokumentacji PostgreSQL.
        # Najpierw budujemy GIN, potem dopiero kasujemy GiST — w razie
        # przerwania wyszukiwanie cały czas ma jakiś indeks.
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "bpp_rekord_mat_search_index_gin "
            "ON bpp_rekord_mat USING GIN (search_index)",
            "DROP INDEX CONCURRENTLY IF EXISTS bpp_rekord_mat_search_index_gin",
        ),
        migrations.RunSQL(
            "DROP INDEX CONCURRENTLY IF EXISTS bpp_rekord_mat_search_index_idx",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "bpp_rekord_mat_search_index_idx "
            "ON bpp_rekord_mat USING GIST (search_index)",
        ),
    ]
