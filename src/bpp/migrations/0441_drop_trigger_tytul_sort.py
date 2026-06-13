from pathlib import Path

from django.db import connection, migrations


def _exec_sql_file(filename):
    sql_file = Path(__file__).parent / filename
    with open(sql_file) as f:
        sql = f.read()
    # connection.cursor() — w reverse plpython3u sa znaki `%`, ktore
    # schema_editor probowalby interpretowac jako placeholdery parametrow.
    with connection.cursor() as cursor:
        cursor.execute(sql)


def drop_trigger(apps, schema_editor):
    _exec_sql_file("0441_drop_trigger_tytul_sort.sql")


def restore_trigger(apps, schema_editor):
    # Reverse: przywroc funkcje + triggery plpython3u (wymaga plpython3u).
    _exec_sql_file("0441_drop_trigger_tytul_sort_reverse.sql")


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0440_port_plpython_to_plpgsql"),
    ]

    operations = [
        migrations.RunPython(drop_trigger, restore_trigger),
    ]
