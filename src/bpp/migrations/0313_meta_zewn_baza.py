# Generated by Django 3.0.14 on 2022-02-27 20:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0312_przypieta"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="wydawnictwo_ciagle_zewnetrzna_baza_danych",
            options={
                "verbose_name": "powiązanie wyd. ciągłego z zewn. bazą danych",
                "verbose_name_plural": "powiązania wyd. ciągłych z zewn. bazami danych",
            },
        ),
        migrations.AlterModelOptions(
            name="wydawnictwo_zwarte_zewnetrzna_baza_danych",
            options={
                "verbose_name": "powiązanie wyd. zwartego z zewn. bazami danych",
                "verbose_name_plural": "powiązania wyd. zwartych z zewn. bazami danych",
            },
        ),
    ]