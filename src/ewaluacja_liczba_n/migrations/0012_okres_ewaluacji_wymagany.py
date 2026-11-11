"""Okres ewaluacji: NOT NULL + unikalność per okres; limit udziałów za cały
okres liczony z długości okresu (``clean``), a nie stałym walidatorem."""

import django.db.models.deletion
from django.db import migrations, models

import ewaluacja_liczba_n.fields
import ewaluacja_liczba_n.models

MODELE = (
    "liczbandlauczelni",
    "iloscudzialowdlaautorazacalosc",
    "dyscyplinanieraportowana",
)


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_liczba_n", "0011_okres_ewaluacji"),
    ]

    operations = [
        *[
            migrations.AlterField(
                model_name=nazwa,
                name="okres",
                field=models.ForeignKey(
                    default=ewaluacja_liczba_n.models.domyslny_okres_pk,
                    on_delete=django.db.models.deletion.PROTECT,
                    to="ewaluacja_common.okresewaluacji",
                    verbose_name="okres ewaluacji",
                ),
            )
            for nazwa in MODELE
        ],
        migrations.AlterUniqueTogether(
            name="liczbandlauczelni",
            unique_together={("uczelnia", "dyscyplina_naukowa", "okres")},
        ),
        migrations.AlterUniqueTogether(
            name="iloscudzialowdlaautorazacalosc",
            unique_together={
                ("autor", "dyscyplina_naukowa", "rodzaj_autora", "uczelnia", "okres")
            },
        ),
        migrations.AlterUniqueTogether(
            name="dyscyplinanieraportowana",
            unique_together={("uczelnia", "dyscyplina_naukowa", "okres")},
        ),
        migrations.AlterField(
            model_name="iloscudzialowdlaautorazacalosc",
            name="ilosc_udzialow",
            field=ewaluacja_liczba_n.fields.LiczbaNField(
                decimal_places=2, max_digits=9
            ),
        ),
        migrations.AlterModelOptions(
            name="dyscyplinanieraportowana",
            options={
                "verbose_name": "Dyscyplina nieraportowana",
                "verbose_name_plural": "Dyscypliny nieraportowane",
            },
        ),
    ]
