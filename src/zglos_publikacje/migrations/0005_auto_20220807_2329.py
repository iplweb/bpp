# Generated by Django 3.2.14 on 2022-08-07 21:29

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zglos_publikacje", "0004_auto_20220801_2128"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="zgloszenie_publikacji_autor",
            options={
                "verbose_name": "autor w zgłoszeniu publikacji",
                "verbose_name_plural": "autorzy w zgłoszeniu publikacji",
            },
        ),
        migrations.CreateModel(
            name="Zgloszenie_Publikacji_Plik",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "plik",
                    models.FileField(upload_to="", verbose_name="Plik załącznika"),
                ),
                (
                    "rekord",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="zglos_publikacje.zgloszenie_publikacji",
                    ),
                ),
            ],
            options={
                "verbose_name": "plik zgłoszenia publikacji",
                "verbose_name_plural": "pliki zgłoszeń publikacji",
            },
        ),
    ]
