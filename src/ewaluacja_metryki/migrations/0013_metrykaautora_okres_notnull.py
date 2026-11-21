"""Okres ewaluacji w metrykach (krok 2 z 2): ``NOT NULL`` + unikalność
(autor, dyscyplina, uczelnia, okres) — metryki różnych okresów współistnieją.
"""

import django.db.models.deletion
from django.db import migrations, models

import ewaluacja_metryki.models


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_metryki", "0012_metrykaautora_okres"),
    ]

    operations = [
        migrations.AlterField(
            model_name="metrykaautora",
            name="okres",
            field=models.ForeignKey(
                default=ewaluacja_metryki.models._domyslny_okres_pk,
                help_text="Okres ewaluacji, za który policzono metrykę",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="metryki_autorow",
                to="ewaluacja_common.okresewaluacji",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="metrykaautora",
            unique_together={("autor", "dyscyplina_naukowa", "uczelnia", "okres")},
        ),
    ]
