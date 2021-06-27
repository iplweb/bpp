# Generated by Django 3.0.14 on 2021-05-03 22:14

from django.db import migrations

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):

    dependencies = [
        ("rozbieznosci_dyscyplin", "0008_recreate"),
        ("bpp", "0278_autorzy_profil_orcid"),
    ]

    operations = [
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql(
                "0002_rok_2017_i_wyzej", app_name="rozbieznosci_dyscyplin"
            )
        )
    ]