# Generated by Django 3.0.14 on 2021-07-13 09:17

from django.db import migrations

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0278_autorzy_profil_orcid"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="wydawnictwo_ciagle",
            name="ostatnio_zmieniony_dla_pbn",
        ),
        migrations.RemoveField(
            model_name="wydawnictwo_zwarte",
            name="ostatnio_zmieniony_dla_pbn",
        ),
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql(
                "0279_usun_ost_akt_pbn", app_name="bpp"
            ),
        ),
        # Odbudowanie tabeli rekord_mat spowoduje skasowanie bpp_uczelnia_ewaluacja_view,
        # stąd potrzeba zaciągnąć ten plik z poprzednich migracji:
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql("0207_uczelnia_analiza_view")
        ),
    ]
