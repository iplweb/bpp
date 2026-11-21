from django.db import migrations, models
import django.db.models.deletion

import ewaluacja_optymalizacja.okres


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_optymalizacja", "0018_okres_ewaluacji_dane"),
    ]

    operations = [
        migrations.AlterField(
            model_name="optimizationrun",
            name="okres",
            field=models.ForeignKey(
                default=ewaluacja_optymalizacja.okres.domyslny_okres_pk,
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AlterField(
            model_name="unpinningopportunity",
            name="okres",
            field=models.ForeignKey(
                default=ewaluacja_optymalizacja.okres.domyslny_okres_pk,
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
        migrations.AlterField(
            model_name="disciplineswapopportunity",
            name="okres",
            field=models.ForeignKey(
                default=ewaluacja_optymalizacja.okres.domyslny_okres_pk,
                on_delete=django.db.models.deletion.PROTECT,
                to="ewaluacja_common.okresewaluacji",
                verbose_name="Okres ewaluacji",
            ),
        ),
    ]
