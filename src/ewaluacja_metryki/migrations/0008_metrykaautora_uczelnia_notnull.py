import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Ustaw MetrykaAutora.uczelnia jako NOT NULL.

    Poprzednia migracja 0006 wykonała backfill: wszystkie wiersze mają już
    uczelnia != NULL (lub zostały usunięte). Teraz usuwamy null=True/blank=True
    z definicji pola — zmiana jest bezpieczna.

    StatusGenerowania.uczelnia pozostaje nullable — patrz komentarz w models.py.
    """

    dependencies = [
        ("bpp", "0428_cpd_uczelnia_not_null"),
        ("ewaluacja_metryki", "0007_statusgenerowania_uczelnia"),
    ]

    operations = [
        migrations.AlterField(
            model_name="metrykaautora",
            name="uczelnia",
            field=models.ForeignKey(
                help_text="Uczelnia, dla której policzono metrykę (multi-hosted)",
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.uczelnia",
            ),
        ),
    ]
