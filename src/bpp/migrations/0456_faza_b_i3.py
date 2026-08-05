"""Faza B / issue #438 — I-3.

Uogólnienie metryczki historycznej ``Jednostka_Wydzial`` (kiedy jednostka była
w którym WYDZIALE) na ``Jednostka_Rodzic`` (kiedy miała którego RODZICA):

1. ``RenameModel`` Jednostka_Wydzial → Jednostka_Rodzic (rename tabeli; check /
   exclude constraints i FK jadą z tabelą — nie referują pola ``wydzial``).
2. ``AddField`` ``parent`` (FK→Jednostka, nullable) — węzeł-rodzic.
3. ``RunPython`` naiwny backfill: ``parent`` = węzeł-lustro o
   ``legacy_wydzial_id == entry.wydzial_id``. Prawdziwe przepisanie historii
   sub-jednostek na krawędź realnego rodzica robi I-4.
4. ``RemoveField`` ``wydzial`` — pole ``Jednostka.wydzial`` (FK→Wydzial) ORAZ
   model ``Wydzial`` NADAL istnieją; usuwamy tylko pole na metryczce.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_parent(apps, schema_editor):
    """Dla KAŻDEGO wpisu ``Jednostka_Rodzic`` ustaw ``parent`` = węzeł
    ``Jednostka`` o ``legacy_wydzial_id == entry.wydzial_id``.

    Mapa budowana raz (bez N+1). Brak węzła dla danego ``wydzial_id`` nie
    powinien się zdarzyć (I-2 tworzy węzły dla wszystkich Wydzial) — wtedy
    zostawiamy ``parent=NULL`` i logujemy, ale NIE wywalamy migracji.
    """
    Jednostka = apps.get_model("bpp", "Jednostka")
    Jednostka_Rodzic = apps.get_model("bpp", "Jednostka_Rodzic")

    mapa = dict(
        Jednostka.objects.filter(legacy_wydzial_id__isnull=False).values_list(
            "legacy_wydzial_id", "id"
        )
    )

    for entry in Jednostka_Rodzic.objects.all().iterator():
        node_id = mapa.get(entry.wydzial_id)
        if node_id is None:
            print(
                f"[0456_faza_b_i3] brak węzła-lustra dla wydzial_id="
                f"{entry.wydzial_id} (wpis {entry.pk}); parent=NULL"
            )
            continue
        Jednostka_Rodzic.objects.filter(pk=entry.pk).update(parent_id=node_id)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0455_faza_b_i2"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Jednostka_Wydzial",
            new_name="Jednostka_Rodzic",
        ),
        migrations.AlterModelOptions(
            name="jednostka_rodzic",
            options={
                "ordering": ("-od",),
                "verbose_name": "powiązanie jednostka-rodzic",
                "verbose_name_plural": "powiązania jednostka-rodzic",
            },
        ),
        migrations.AddField(
            model_name="jednostka_rodzic",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="jednostka_rodzic_parent_set",
                to="bpp.jednostka",
            ),
        ),
        migrations.RunPython(backfill_parent, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="jednostka_rodzic",
            name="wydzial",
        ),
    ]
