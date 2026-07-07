"""Faza B / issue #438 — II-2: przepięcie ``Import_Dyscyplin_Row.wydzial``
``Wydzial``→``Jednostka`` (SET_NULL, pole nullable).

Three-step (BŁĄD #2 z review kolejności migracji): ``AlterField wydzial →
IntegerField`` (zrzuca stary constraint FK→Wydzial, zachowuje wartości =
stare ``Wydzial.id``; ``db_column="wydzial_id"`` zostaje — nie ma fizycznego
rename kolumny) → ``RunPython`` remap ``wydzial`` →
``Jednostka(legacy_wydzial_id=old).pk`` (węzeł-lustro; mapa budowana raz,
bez N+1) → ``AlterField wydzial → ForeignKey("bpp.Jednostka", SET_NULL, …)``.

UWAGA: na etapie IntegerField ORM-owa nazwa lookupu/atrybutu to ``wydzial``
(NIE ``wydzial_id``!) — ``db_column`` zmienia tylko fizyczną nazwę kolumny
SQL. ``_id`` w atrybucie dostają tylko FK/O2O.

Polityka „unmappable" (brak węzła-lustra dla użytego ``Wydzial``): pole jest
nullable, więc po prostu ``NULL`` + log (spójne z ``Patent.wydzial`` w
``bpp/migrations/0460_faza_b_ii2_repoint.py``).
"""

import django.db.models.deletion
from django.db import migrations, models


def remap_import_dyscyplin_row_wydzial(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    Import_Dyscyplin_Row = apps.get_model("import_dyscyplin", "Import_Dyscyplin_Row")

    mapa = dict(
        Jednostka.objects.filter(legacy_wydzial_id__isnull=False).values_list(
            "legacy_wydzial_id", "id"
        )
    )

    uzyte = list(
        Import_Dyscyplin_Row.objects.filter(wydzial__isnull=False)
        .values_list("wydzial", flat=True)
        .distinct()
    )
    brakujace = sorted({w for w in uzyte if w not in mapa})
    if brakujace:
        print(
            "[0024_faza_b_ii2] Import_Dyscyplin_Row.wydzial: brak węzła-lustra "
            f"dla wydzial_id w {brakujace} — ustawiam NULL."
        )
        Import_Dyscyplin_Row.objects.filter(wydzial__in=brakujace).update(wydzial=None)

    # Snapshot pk PRZED update-ami (spójne z ``0026``/``0460``): naiwne
    # ``filter(wydzial=old).update(wydzial=new)`` nadpisuje TĘ SAMĄ kolumnę, po
    # której selektuje — gdy pk węzła-lustra (new_id) pokrywa się z pk innego,
    # późniejszego wydziału (old_id), wiersz zostaje przepięty DRUGI raz (cicha
    # korupcja FK). Update po zamrożonym pk jest odporny.
    plan = {
        old_id: list(
            Import_Dyscyplin_Row.objects.filter(wydzial=old_id)
            .order_by()  # zrzuca Meta.ordering — spójne z resztą
            .values_list("pk", flat=True)
        )
        for old_id in mapa
    }
    for old_id, new_id in mapa.items():
        Import_Dyscyplin_Row.objects.filter(pk__in=plan[old_id]).update(wydzial=new_id)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0460_faza_b_ii2_repoint"),
        ("import_dyscyplin", "0023_remove_null_from_string_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="import_dyscyplin_row",
            name="wydzial",
            field=models.IntegerField(null=True, db_column="wydzial_id"),
        ),
        migrations.RunPython(
            remap_import_dyscyplin_row_wydzial, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="import_dyscyplin_row",
            name="wydzial",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="bpp.jednostka",
            ),
        ),
    ]
