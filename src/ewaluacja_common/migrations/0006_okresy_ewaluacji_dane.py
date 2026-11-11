"""Okresy ewaluacji na start: 2022–2025 (obowiązujący) i 2026–2030.

2026–2030 wg projektu nowelizacji ustawy z 2026 r. (okres wydłużony z 4 do
5 lat) — do czasu jej uchwalenia to założenie; w razie zmiany wystarczy
poprawić wpis w adminie.
"""

from django.db import migrations

OKRESY = [
    (2022, 2025, "Rozporządzenie MNiSW z 22 lutego 2019 r. w sprawie ewaluacji."),
    (
        2026,
        2030,
        "Wg projektu nowelizacji ustawy (2026 r.: okres 5-letni). Do czasu "
        "nowego rozporządzenia punkty i sloty liczone wg zasad 2022–2025.",
    ),
]


def dodaj(apps, schema_editor):
    OkresEwaluacji = apps.get_model("ewaluacja_common", "OkresEwaluacji")
    for rok_od, rok_do, uwagi in OKRESY:
        OkresEwaluacji.objects.get_or_create(
            rok_od=rok_od, defaults={"rok_do": rok_do, "uwagi": uwagi}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ewaluacja_common", "0005_okres_ewaluacji"),
    ]

    operations = [
        migrations.RunPython(dodaj, migrations.RunPython.noop),
    ]
