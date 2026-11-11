"""Liczba N, udziały za cały okres i dyscypliny nieraportowane — per okres
ewaluacji.

Istniejące wiersze (liczone dotąd zawsze dla 2022–2025, w tym ręcznie
wpisane sankcje) trafiają do okresu 2022–2025. Pole dodajemy jako nullable,
wypełniamy danymi, a NOT NULL i unikalność dokłada 0012 (osobna migracja =
osobna transakcja; ALTER TABLE po UPDATE kolumny FK w tej samej transakcji
pada na PostgreSQL przez oczekujące triggery). Callable default (okres
domyślny wg bieżącego roku) przypisałby stare dane do 2026–2030.
"""

import django.db.models.deletion
from django.db import migrations, models

MODELE = (
    "liczbandlauczelni",
    "iloscudzialowdlaautorazacalosc",
    "dyscyplinanieraportowana",
)


def przypisz_okres_2022_2025(apps, schema_editor):
    OkresEwaluacji = apps.get_model("ewaluacja_common", "OkresEwaluacji")
    okres, _ = OkresEwaluacji.objects.get_or_create(
        rok_od=2022, defaults={"rok_do": 2025}
    )
    for nazwa in MODELE:
        Model = apps.get_model("ewaluacja_liczba_n", nazwa)
        Model.objects.filter(okres__isnull=True).update(okres=okres)


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_common", "0006_okresy_ewaluacji_dane"),
        ("ewaluacja_liczba_n", "0010_merge_20260604_1952"),
    ]

    operations = [
        *[
            migrations.AddField(
                model_name=nazwa,
                name="okres",
                field=models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to="ewaluacja_common.okresewaluacji",
                    verbose_name="okres ewaluacji",
                ),
            )
            for nazwa in MODELE
        ],
        migrations.RunPython(przypisz_okres_2022_2025, migrations.RunPython.noop),
    ]
