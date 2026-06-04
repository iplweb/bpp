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
        ("bpp", "0421_cache_trigger_pk_filter"),
    ]

    operations = [
        migrations.RunPython(
            _run("0422_drop_unused_cache_indexes.sql"),
            _run("0422_drop_unused_cache_indexes_reverse.sql"),
        ),
    ]
