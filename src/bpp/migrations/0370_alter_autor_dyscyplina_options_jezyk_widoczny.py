# Generated by Django 4.2.19 on 2025-03-03 20:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0369_wyd_zwarte_nadrzedne_w_pbn"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="autor_dyscyplina",
            options={
                "ordering": ("rok",),
                "verbose_name": "powiązanie autor-dyscyplina",
                "verbose_name_plural": "powiązania autor-dyscyplina",
            },
        ),
        migrations.AddField(
            model_name="jezyk",
            name="widoczny",
            field=models.BooleanField(default=True),
        ),
    ]
