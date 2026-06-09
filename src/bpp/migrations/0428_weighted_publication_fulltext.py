from pathlib import Path

from django.db import connection, migrations


def load_sql(apps, schema_editor):
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
