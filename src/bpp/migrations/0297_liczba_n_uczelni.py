# Generated by Django 3.0.14 on 2021-10-10 21:08

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0296_nulltest_szablonopisu"),
    ]

    operations = [
        migrations.CreateModel(
            name="Ewaluacja2021LiczbaNDlaUczelni",
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
                ("liczba_n", models.DecimalField(decimal_places=4, max_digits=9)),
                (
                    "dyscyplina_naukowa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="bpp.Dyscyplina_Naukowa",
                    ),
                ),
                (
                    "uczelnia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="bpp.Uczelnia"
                    ),
                ),
            ],
            options={
                "verbose_name": "Liczba N dla uczelni",
                "verbose_name_plural": "Liczby N dla uczelni",
                "unique_together": {("uczelnia", "dyscyplina_naukowa")},
            },
        ),
    ]
