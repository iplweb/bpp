"""Istniejące wyniki optymalizacji pochodzą z okresu 2022–2025 — przypisz
je do tego okresu (a statusy zadań, które kiedykolwiek ruszyły, też)."""

from django.db import migrations

MODELE_WYNIKOW = [
    "OptimizationRun",
    "UnpinningOpportunity",
    "DisciplineSwapOpportunity",
]

MODELE_STATUSU = [
    "StatusOptymalizacjiBulk",
    "StatusUnpinningAnalyzy",
    "StatusDisciplineSwapAnalysis",
    "StatusPrzegladarkaRecalc",
]


def przypisz(apps, schema_editor):
    OkresEwaluacji = apps.get_model("ewaluacja_common", "OkresEwaluacji")
    okres, _ = OkresEwaluacji.objects.get_or_create(
        rok_od=2022, defaults={"rok_do": 2025}
    )
    for nazwa in MODELE_WYNIKOW:
        model = apps.get_model("ewaluacja_optymalizacja", nazwa)
        model.objects.filter(okres__isnull=True).update(okres=okres)
    for nazwa in MODELE_STATUSU:
        model = apps.get_model("ewaluacja_optymalizacja", nazwa)
        model.objects.filter(okres__isnull=True, data_rozpoczecia__isnull=False).update(
            okres=okres
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_optymalizacja", "0017_okres_ewaluacji"),
    ]

    operations = [
        migrations.RunPython(przypisz, migrations.RunPython.noop),
    ]
