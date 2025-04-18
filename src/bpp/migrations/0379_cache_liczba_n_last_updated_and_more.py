# Generated by Django 4.2.19 on 2025-03-18 14:56

from django.db import migrations, models

from bpp.migration_util import load_custom_sql


def utworz_obiekt_liczba_cache_liczba_n(apps, schema_editor):
    Cache_Liczba_N_Last_Updated = apps.get_model("bpp", "Cache_Liczba_N_Last_Updated")
    Cache_Liczba_N_Last_Updated.objects.get_or_create(pk=1, wymaga_przeliczenia=True)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0378_alter_praca_doktorska_pbn_uid_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cache_Liczba_N_Last_Updated",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("wymaga_przeliczenia", models.BooleanField(default=True)),
            ],
        ),
        migrations.RunPython(utworz_obiekt_liczba_cache_liczba_n),
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql("0379_autor_dyscyplina_update_trigger")
        ),
    ]
