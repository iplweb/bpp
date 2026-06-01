from pathlib import Path

from django.db import connection, migrations


def load_sql(apps, schema_editor):
    sql_file = Path(__file__).parent / "0418_autor_dyscyplina_trigger_on_conflict.sql"
    with open(sql_file) as f:
        sql = f.read()
    # connection.cursor() zamiast schema_editor.execute() — w cqueue sa `%s`,
    # ktore schema_editor probowalby interpretowac jako placeholdery parametrow.
    with connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0417_remove_uczelnia_pokazuj_raport_autorow_and_more"),
    ]

    operations = [
        migrations.RunPython(load_sql, migrations.RunPython.noop),
    ]
