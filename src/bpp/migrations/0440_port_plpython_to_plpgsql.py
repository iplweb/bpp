from pathlib import Path

from django.db import connection, migrations


def _exec_sql_file(filename):
    sql_file = Path(__file__).parent / filename
    with open(sql_file) as f:
        sql = f.read()
    # connection.cursor() zamiast schema_editor.execute() — w ciele funkcji
    # (format('...%I...'), a w reverse plpython3u znaki `%`) PostgreSQL/psycopg
    # przez schema_editor probowalby interpretowac `%` jako placeholdery.
    with connection.cursor() as cursor:
        cursor.execute(sql)


def load_sql(apps, schema_editor):
    _exec_sql_file("0440_port_plpython_to_plpgsql.sql")


def unload_sql(apps, schema_editor):
    # Reverse: przywroc wersje plpython3u (wymaga rozszerzenia plpython3u,
    # ktore jest jeszcze obecne az do osobnego DROP EXTENSION w finalnym PR).
    _exec_sql_file("0440_port_plpython_to_plpgsql_reverse.sql")


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0431_search_index_gin"),
    ]

    operations = [
        migrations.RunPython(load_sql, unload_sql),
    ]
