# Generated by Django 3.0.14 on 2021-08-20 14:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0289_data_oswiadczenia"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bppmultiseekvisibility",
            name="field_name",
            field=models.CharField(
                db_index=True,
                max_length=50,
                unique=True,
                verbose_name="Systemowa nazwa pola",
            ),
        ),
        migrations.AlterField(
            model_name="bppmultiseekvisibility",
            name="label",
            field=models.CharField(max_length=200, verbose_name="Nazwa pola"),
        ),
        migrations.AlterField(
            model_name="bppmultiseekvisibility",
            name="public",
            field=models.BooleanField(
                default=True, verbose_name="Widoczne dla niezalogowanych"
            ),
        ),
        migrations.AlterField(
            model_name="bppmultiseekvisibility",
            name="sort_order",
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name="Kolejność sortowania"
            ),
        ),
    ]