from pathlib import Path

from django.db import connection, migrations


def _run(filename):
    def inner(apps, schema_editor):
        sql_file = Path(__file__).parent / filename
        with open(sql_file) as f:
            sql = f.read()
        with connection.cursor() as cursor:
            cursor.execute(sql)

    return inner


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0424_alter_autor_dyscyplina_autor_and_more"),
    ]

    operations = [
        migrations.RunPython(
            _run("0425_drop_redundant_raw_indexes.sql"),
            _run("0425_drop_redundant_raw_indexes_reverse.sql"),
        ),
    ]
