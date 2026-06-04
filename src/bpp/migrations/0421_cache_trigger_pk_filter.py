from pathlib import Path

from django.db import connection, migrations


def load_sql(apps, schema_editor):
    sql_file = Path(__file__).parent / "0421_cache_trigger_pk_filter.sql"
    with open(sql_file) as f:
        sql = f.read()
    # connection.cursor() zamiast schema_editor.execute() — w ciele funkcji
    # plpython3u sa znaki `%`, ktore schema_editor probowalby interpretowac
    # jako placeholdery parametrow.
    with connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0420_autor_pokazuj_siec_powiazan_and_more"),
    ]

    operations = [
        migrations.RunPython(load_sql, migrations.RunPython.noop),
    ]
