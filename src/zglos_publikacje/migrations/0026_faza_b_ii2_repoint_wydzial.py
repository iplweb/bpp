"""Faza B / issue #438 — II-2: przepięcie
``Obslugujacy_Zgloszenia_Wydzialow.wydzial`` ``Wydzial``→``Jednostka``
(CASCADE, pole NOT NULL).

Three-step (BŁĄD #2 z review kolejności migracji): ``AlterField wydzial →
IntegerField`` (zrzuca stary constraint FK→Wydzial, zachowuje wartości =
stare ``Wydzial.id``; ``db_column="wydzial_id"`` zostaje — nie ma
fizycznego rename kolumny) → ``RunPython`` remap ``wydzial`` →
``Jednostka(legacy_wydzial_id=old).pk`` (węzeł-lustro; mapa budowana raz,
bez N+1) → ``AlterField wydzial → ForeignKey("bpp.Jednostka", CASCADE, …)``.

UWAGA: na etapie IntegerField ORM-owa nazwa lookupu/atrybutu to ``wydzial``
(NIE ``wydzial_id``!) — ``db_column`` zmienia tylko fizyczną nazwę kolumny
SQL. ``_id`` w atrybucie dostają tylko FK/O2O.

Polityka „unmappable" (brak węzła-lustra dla użytego ``Wydzial``): pole jest
NOT NULL, więc nie ma jak ustawić ``NULL`` — **skip**: usuń niemapowalne
wiersze + log (spójne z ``Opi_2012_Afiliacja_Do_Wydzialu.wydzial`` w
``bpp/migrations/0460_faza_b_ii2_repoint.py``). Wiersz „obsługujący
zgłoszenia dla wydziału X" bez sensownego X jest bezużyteczny — usunięcie
jest bezpieczne (użytkownik po prostu przestaje obsługiwać nieistniejący
wydział).
"""

import django.db.models.deletion
from django.db import migrations, models


def remap_obslugujacy_wydzial(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    Obslugujacy_Zgloszenia_Wydzialow = apps.get_model(
        "zglos_publikacje", "Obslugujacy_Zgloszenia_Wydzialow"
    )

    mapa = dict(
        Jednostka.objects.filter(legacy_wydzial_id__isnull=False).values_list(
            "legacy_wydzial_id", "id"
        )
    )

    # ``.order_by()`` (bez argumentów) zrzuca ``Meta.ordering`` modelu —
    # domyślne ``("user__username", "wydzial__nazwa")`` nie da się
    # rozwiązać na tym etapie (``wydzial`` to jeszcze IntegerField, nie
    # relacja) i bez tego SELECT DISTINCT rzuca ``FieldError``.
    uzyte = list(
        Obslugujacy_Zgloszenia_Wydzialow.objects.order_by()
        .values_list("wydzial", flat=True)
        .distinct()
    )
    brakujace = sorted({w for w in uzyte if w not in mapa})
    if brakujace:
        usuniete, _ = Obslugujacy_Zgloszenia_Wydzialow.objects.filter(
            wydzial__in=brakujace
        ).delete()
        print(
            "[0026_faza_b_ii2] Obslugujacy_Zgloszenia_Wydzialow.wydzial: brak "
            f"węzła-lustra dla wydzial_id w {brakujace} — usunięto "
            f"{usuniete} wiersz(y)."
        )

    # Snapshot pk PRZED update-ami: naiwne
    # ``filter(wydzial=old).update(wydzial=new)`` nadpisuje TĘ SAMĄ kolumnę, po
    # której selektuje — gdy pk węzła-lustra (new_id) pokrywa się z pk innego,
    # późniejszego wydziału (old_id), wiersz zostaje przepięty DRUGI raz (cicha
    # korupcja FK routingu zgłoszeń). Update po zamrożonym pk jest odporny.
    plan = {
        old_id: list(
            Obslugujacy_Zgloszenia_Wydzialow.objects.filter(
                wydzial=old_id
            ).values_list("pk", flat=True)
        )
        for old_id in mapa
    }
    for old_id, new_id in mapa.items():
        Obslugujacy_Zgloszenia_Wydzialow.objects.filter(pk__in=plan[old_id]).update(
            wydzial=new_id
        )


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0460_faza_b_ii2_repoint"),
        ("zglos_publikacje", "0025_alter_obslugujacy_zgloszenia_wydzialow_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="obslugujacy_zgloszenia_wydzialow",
            name="wydzial",
            field=models.IntegerField(db_column="wydzial_id"),
        ),
        migrations.RunPython(remap_obslugujacy_wydzial, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="obslugujacy_zgloszenia_wydzialow",
            name="wydzial",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.jednostka",
                verbose_name="Wydział",
            ),
        ),
    ]
