"""Okres ewaluacji w wynikach optymalizacji i statusach zadań.

Pola dodawane jako nullable; wypełnia je 0018, a 0019 robi je wymaganymi
(w modelach wyników).
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_common", "0006_okresy_ewaluacji_dane"),
        ("ewaluacja_optymalizacja", "0016_statusodpinaniawszystkich"),
    ]

    operations = [
        migrations.AddField(
            model_name="optimizationrun",
            name="okres",
            field=models.ForeignKey(
                blank=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AddField(
            model_name="unpinningopportunity",
            name="okres",
            field=models.ForeignKey(
                blank=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AddField(
            model_name="disciplineswapopportunity",
            name="okres",
            field=models.ForeignKey(
                blank=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AddField(
            model_name="statusoptymalizacjibulk",
            name="okres",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Okres, którego dotyczy ostatnio uruchomione zadanie",
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AddField(
            model_name="statusunpinninganalyzy",
            name="okres",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Okres, którego dotyczy ostatnio uruchomione zadanie",
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AddField(
            model_name="statusdisciplineswapanalysis",
            name="okres",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Okres, którego dotyczy ostatnio uruchomione zadanie",
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AddField(
            model_name="statusprzegladarkarecalc",
            name="okres",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Okres, którego dotyczy ostatnio uruchomione zadanie",
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
    ]
