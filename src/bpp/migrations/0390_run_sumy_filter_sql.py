# Generated migration file

from django.db import migrations

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0389_alter_uczelnia_uzywaj_wydzialow"),
    ]

    operations = [
        migrations.RunSQL(
            sql=load_custom_sql("0390_add_filters_to_sumy_view"),
            reverse_sql="-- Reverse migration not implemented",
        ),
    ]
