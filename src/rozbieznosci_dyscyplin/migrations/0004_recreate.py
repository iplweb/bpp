# Generated by Django 2.2.10 on 2020-03-04 23:17

from django.db import migrations
from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):

    dependencies = [
        (
            "rozbieznosci_dyscyplin",
            "0003_brakprzypisaniaview_rozbiezneprzypisaniaview_rozbieznosciview",
        ),
        ("bpp", "0201_rekord_mat_z_www"),
    ]

    operations = [
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql(
                "0002_rok_2017_i_wyzej", app_name="rozbieznosci_dyscyplin"
            )
        )
    ]
