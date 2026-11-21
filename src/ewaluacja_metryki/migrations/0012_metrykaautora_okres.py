"""Okres ewaluacji w metrykach (krok 1 z 2): kolumna ``okres`` + dane.

Istniejące metryki liczono dla 2022–2025, więc dostają ten okres. ``NOT NULL``
i nowa unikalność są w ``0013`` — osobna migracja, bo ``UPDATE`` kolumny z FK
zostawia w PostgreSQL oczekujące zdarzenia wyzwalaczy i ``ALTER TABLE`` w tej
samej transakcji się wywala.
"""

import django.db.models.deletion
from django.db import migrations, models


def przypisz_okres_2022(apps, schema_editor):
    OkresEwaluacji = apps.get_model("ewaluacja_common", "OkresEwaluacji")
    MetrykaAutora = apps.get_model("ewaluacja_metryki", "MetrykaAutora")
    StatusGenerowania = apps.get_model("ewaluacja_metryki", "StatusGenerowania")

    if not MetrykaAutora.objects.exists() and not StatusGenerowania.objects.exists():
        return

    okres, _ = OkresEwaluacji.objects.get_or_create(
        rok_od=2022, defaults={"rok_do": 2025}
    )
    MetrykaAutora.objects.filter(okres__isnull=True).update(okres=okres)
    StatusGenerowania.objects.filter(okres__isnull=True).update(okres=okres)


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_common", "0006_okresy_ewaluacji_dane"),
        ("ewaluacja_metryki", "0011_statusgenerowania_jeden_wiersz_bez_uczelni"),
    ]

    operations = [
        migrations.AddField(
            model_name="metrykaautora",
            name="okres",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="metryki_autorow",
                to="ewaluacja_common.okresewaluacji",
                help_text="Okres ewaluacji, za który policzono metrykę",
            ),
        ),
        migrations.AddField(
            model_name="statusgenerowania",
            name="okres",
            field=models.ForeignKey(
                blank=True,
                help_text="Okres ewaluacji ostatniego (lub trwającego) generowania",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="ewaluacja_common.okresewaluacji",
            ),
        ),
        migrations.RunPython(przypisz_okres_2022, migrations.RunPython.noop),
    ]
