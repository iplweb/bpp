from django.db import migrations

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):
    dependencies = [
    ]

    operations = [
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql("0001_widok_rozbieznosci", app_name="rozbieznosci_dyscyplin")
        ),

    ]
