# Generated by Django 4.2.14 on 2024-07-26 17:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0348_remove_uczelnia_pokazuj_raport_dla_komisji_centralnej_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="uczelnia",
            name="ranking_autorow_bez_kol_naukowych",
            field=models.BooleanField(
                default=True, verbose_name="Ranking autorów bez kół naukowych"
            ),
        ),
    ]
