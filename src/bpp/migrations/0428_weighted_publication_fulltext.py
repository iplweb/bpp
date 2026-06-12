from pathlib import Path

from django.db import connection, migrations


def load_sql(apps, schema_editor):
    """Instaluje wazone funkcje fulltext (CREATE OR REPLACE FUNCTION).

    Celowo NIE przelicza search_index dla istniejacych wierszy:
    pelnotabelowe ``UPDATE ... SET id = id`` w jednej transakcji odpalalo
    na kazdym wierszu triggery AFTER — bpp_refresh_cache() bierze
    pg_advisory_xact_lock(ct, id) per rekord (osobny wpis w lock table,
    trzymany do konca transakcji), a triggery denorm otwieraja
    subtransakcje per wiersz (BEGIN...EXCEPTION). Na duzych bazach
    wyczerpywalo to pamiec wspoldzielona PostgreSQL ("out of shared
    memory", HINT: max_locks_per_transaction).

    Istniejace wiersze przelicza polecenie ``rebuild_search_index``
    (batchami, z wylaczonymi triggerami) — do uruchomienia recznie lub
    z nocnego crona. Nowe/edytowane rekordy dostaja wazony wektor od
    razu przez triggery ts_post_*_search.
    """
    sql_file = Path(__file__).parent / "0428_weighted_publication_fulltext.sql"
    with open(sql_file) as f:
        sql = f.read()
    with connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0427_merge_20260604_1838"),
    ]

    operations = [
        migrations.RunPython(load_sql, migrations.RunPython.noop),
    ]
