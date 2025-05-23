# Generated by Django 4.2.19 on 2025-05-11 18:49

import django.core.validators
from django.db import migrations

import ewaluacja2021.fields


class Migration(migrations.Migration):

    dependencies = [
        ("ewaluacja2021", "0012_liczbandlauczelni_2022_2025_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iloscudzialowdlaautora",
            name="ilosc_udzialow",
            field=ewaluacja2021.fields.LiczbaNField(
                decimal_places=2,
                max_digits=9,
                validators=[django.core.validators.MaxValueValidator(4)],
            ),
        ),
        migrations.AlterField(
            model_name="iloscudzialowdlaautora",
            name="ilosc_udzialow_monografie",
            field=ewaluacja2021.fields.LiczbaNField(decimal_places=2, max_digits=9),
        ),
        migrations.AlterField(
            model_name="iloscudzialowdlaautora_2022_2025",
            name="ilosc_udzialow",
            field=ewaluacja2021.fields.LiczbaNField(
                decimal_places=2,
                max_digits=9,
                validators=[django.core.validators.MaxValueValidator(4)],
            ),
        ),
        migrations.AlterField(
            model_name="iloscudzialowdlaautora_2022_2025",
            name="ilosc_udzialow_monografie",
            field=ewaluacja2021.fields.LiczbaNField(decimal_places=2, max_digits=9),
        ),
        migrations.AlterField(
            model_name="liczbandlauczelni",
            name="liczba_n",
            field=ewaluacja2021.fields.LiczbaNField(decimal_places=2, max_digits=9),
        ),
        migrations.AlterField(
            model_name="liczbandlauczelni_2022_2025",
            name="liczba_n",
            field=ewaluacja2021.fields.LiczbaNField(decimal_places=2, max_digits=9),
        ),
    ]
