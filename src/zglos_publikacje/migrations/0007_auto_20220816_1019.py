# Generated by Django 3.2.15 on 2022-08-16 08:19

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zglos_publikacje", "0006_auto_20220815_1752"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="zgloszenie_publikacji_autor",
            options={
                "ordering": ("kolejnosc",),
                "verbose_name": "autor w zgłoszeniu publikacji",
                "verbose_name_plural": "autorzy w zgłoszeniu publikacji",
            },
        ),
        migrations.AddField(
            model_name="zgloszenie_publikacji",
            name="kod_do_edycji",
            field=models.UUIDField(
                blank=True, default=uuid.uuid4, editable=False, null=True, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="zgloszenie_publikacji",
            name="opl_pub_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=20,
                null=True,
                verbose_name="Kwota brutto (zł)",
            ),
        ),
    ]
