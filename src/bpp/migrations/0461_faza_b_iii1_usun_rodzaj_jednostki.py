"""Faza B / issue #438 — III-1: usunięcie starego CharField
``Jednostka.rodzaj_jednostki`` (+ klasa ``RODZAJ_JEDNOSTKI`` w kodzie modelu,
poza schematem — nie dotyczy migracji).

Dwa kroki:
  1. Idempotentny re-backfill FK ``rodzaj`` z CharField — belt-and-braces.
     0451 (Faza A) i 0459 (Faza B / F1) już to zrobiły, ale to OSTATNI
     moment, w którym CharField istnieje fizycznie w schemacie — każda
     jednostka utworzona/zmodyfikowana między ostatnim re-backfillem a TĄ
     migracją (np. ręcznie w adminie, importem) domyka drift tutaj.
  2. ``RemoveField`` — kolumna znika.

Mapa identyczna z 0451/0459: ``normalna→"Standard"``,
``kolo_naukowe→"Koło naukowe"``.
"""

from django.db import migrations

RODZAJ_CHARFIELD_MAPA = {"normalna": "Standard", "kolo_naukowe": "Koło naukowe"}


def rebackfill_rodzaj_z_charfield(apps, schema_editor):
    """Idempotentnie uzupełnij FK ``rodzaj`` z CharField ``rodzaj_jednostki``
    (WYŁĄCZNIE ``rodzaj_id IS NULL``) — ostatnia szansa przed RemoveField."""
    Jednostka = apps.get_model("bpp", "Jednostka")
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")

    for kod, nazwa in RODZAJ_CHARFIELD_MAPA.items():
        rodzaj = RodzajJednostki.objects.filter(nazwa=nazwa).first()
        if rodzaj is None:
            # Brak wiersza słownika (nietypowa instalacja) — nic do przypięcia.
            continue
        Jednostka.objects.filter(rodzaj__isnull=True, rodzaj_jednostki=kod).update(
            rodzaj=rodzaj
        )


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0460_faza_b_ii2_repoint"),
    ]

    operations = [
        migrations.RunPython(rebackfill_rodzaj_z_charfield, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="jednostka",
            name="rodzaj_jednostki",
        ),
    ]
