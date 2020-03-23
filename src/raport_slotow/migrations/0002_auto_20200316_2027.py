# Generated by Django 2.2.10 on 2020-03-16 19:27

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("raport_slotow", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RaportUczelniaEwaluacjaView",
            fields=[
                (
                    "id",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.PositiveIntegerField(),
                        primary_key=True,
                        serialize=False,
                        size=4,
                    ),
                ),
                ("tytul_oryginalny", models.TextField()),
                (
                    "opis_bibliograficzny_autorzy_cache",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.TextField(), size=None
                    ),
                ),
                ("szczegoly", models.TextField()),
                ("informacje", models.TextField()),
                (
                    "autorzy_z_dyscypliny",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.TextField(), size=None
                    ),
                ),
                ("kolejnosc", models.PositiveSmallIntegerField()),
                ("punkty_kbn", models.DecimalField(decimal_places=2, max_digits=6)),
                (
                    "autor_dyscyplina_procent",
                    models.DecimalField(decimal_places=2, max_digits=5),
                ),
                (
                    "autor_subdyscyplina_procent",
                    models.DecimalField(decimal_places=2, max_digits=5),
                ),
                ("pkdaut", models.DecimalField(decimal_places=4, max_digits=20)),
                ("slot", models.DecimalField(decimal_places=4, max_digits=20)),
            ],
            options={
                "db_table": "bpp_uczelnia_ewaluacja_view",
                "ordering": ("tytul_oryginalny", "rekord_id", "kolejnosc"),
                "managed": False,
            },
        ),
        migrations.AlterModelOptions(
            name="raportzerowyentry",
            options={"managed": False, "ordering": ("autor", "dyscyplina_naukowa")},
        ),
    ]