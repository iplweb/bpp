# Generated by Django 3.0.7 on 2020-07-27 20:28

import bpp.models.const
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("bpp", "0215_auto_20200727_1407"),
    ]

    operations = [
        migrations.CreateModel(
            name="Element_Repozytorium",
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
                ("object_id", models.PositiveIntegerField()),
                ("rodzaj", models.CharField(max_length=200)),
                ("nazwa_pliku", models.CharField(max_length=200)),
                (
                    "tryb_dostepu",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (bpp.models.const.TRYB_DOSTEPU["NIEJAWNY"], "niejawny"),
                            (
                                bpp.models.const.TRYB_DOSTEPU["TYLKO_W_SIECI"],
                                "tylko w sieci",
                            ),
                            (bpp.models.const.TRYB_DOSTEPU["JAWNY"], "jawny"),
                        ]
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.ContentType",
                    ),
                ),
            ],
        ),
    ]