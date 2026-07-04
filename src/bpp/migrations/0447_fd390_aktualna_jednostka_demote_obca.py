from pathlib import Path

from django.db import connection, migrations


def _exec_sql_file(filename):
    sql_file = Path(__file__).parent / filename
    with open(sql_file) as f:
        sql = f.read()
    with connection.cursor() as cursor:
        cursor.execute(sql)


def load_sql(apps, schema_editor):
    _exec_sql_file("0447_fd390_aktualna_jednostka_demote_obca.sql")


def unload_sql(apps, schema_editor):
    _exec_sql_file("0447_fd390_aktualna_jednostka_demote_obca_reverse.sql")


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0446_rzeczownik_tylko_mianownik"),
    ]

    operations = [
        migrations.RunPython(load_sql, unload_sql),
    ]
