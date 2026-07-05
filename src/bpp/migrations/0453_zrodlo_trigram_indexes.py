"""Indeksy GIN trigram na bpp_zrodlo.nazwa / skrot.

Deduplikator źródeł liczy podobieństwo trigramowe nazwy do całej tabeli
źródeł raz na każde skanowane źródło. Bez indeksu GIN trigram jest to
sekwencyjny skan (Postgres NIE użyje GIN dla ``similarity() >= x`` — tylko
dla operatora ``%``). Te indeksy pozwalają prefiltrować kandydatów
operatorem ``%`` (``__trigram_similar``) zamiast pełnego skanu.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0452_jednostka_pola_faza_a"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
                "CREATE INDEX IF NOT EXISTS bpp_zrodlo_nazwa_trgm "
                "ON bpp_zrodlo USING GIN (nazwa gin_trgm_ops);",
                "CREATE INDEX IF NOT EXISTS bpp_zrodlo_skrot_trgm "
                "ON bpp_zrodlo USING GIN (skrot gin_trgm_ops);",
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS bpp_zrodlo_skrot_trgm;",
                "DROP INDEX IF EXISTS bpp_zrodlo_nazwa_trgm;",
            ],
        ),
    ]
