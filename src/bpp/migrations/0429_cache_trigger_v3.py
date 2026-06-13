from pathlib import Path

from django.db import connection, migrations


def load_sql(apps, schema_editor):
    sql_file = Path(__file__).parent / "0429_cache_trigger_v3.sql"
    with open(sql_file) as f:
        sql = f.read()
    # connection.cursor() zamiast schema_editor.execute() — w ciele funkcji
    # plpython3u sa znaki `%`, ktore schema_editor probowalby interpretowac
    # jako placeholdery parametrow.
    with connection.cursor() as cursor:
        cursor.execute(sql)


def unload_sql(apps, schema_editor):
    # Revert: przywroc funkcje v2 (plik 0421 zawiera widoki + funkcje;
    # widoki sa identyczne, wiec ponowne CREATE OR REPLACE jest neutralne).
    sql_file = Path(__file__).parent / "0421_cache_trigger_pk_filter.sql"
    with open(sql_file) as f:
        sql = f.read()
    with connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0428_weighted_publication_fulltext"),
    ]

    operations = [
        migrations.RunPython(load_sql, unload_sql),
    ]
