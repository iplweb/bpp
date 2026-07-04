"""Faza B / issue #438 — II-1 (b): atomowy retarget ``Jednostka.wydzial``.

``Jednostka.wydzial`` przestaje być FK→Wydzial, a staje się zdenormalizowanym
self-FK→Jednostka wskazującym KORZEŃ drzewa (NULL dla jednostek top-level),
utrzymywanym przez ``django-denorm-iplweb``.

Trzy kroki (BŁĄD #2 z review kolejności migracji):
  1. ``AlterField wydzial → IntegerField`` (db_column zostaje ``wydzial_id``) —
     zrzuca stary constraint FK→Wydzial, zachowuje wartości (stare Wydzial.id).
  2. RunPython: dla każdej jednostki policz KORZEŃ wędrówką po ``parent``
     (drzewo gotowe po I-4 / 0457); root → NULL, potomek → pk korzenia.
     NIE ślepy remap starego ``wydzial_id`` — dla zagnieżdżonych z driftem stary
     ``wydzial_id`` ≠ korzeń (BŁĄD #8).
  3. ``AlterField wydzial → ForeignKey("self", SET_NULL, editable=False)`` —
     zamrożona (``deconstruct``) postać denorm-owego pola z ``jednostka.py``.

Okno denorm (BŁĄD #5): ``denorm_drop`` PRZED retargetem, ``denorm_init`` PO —
w jednym commicie, HEAD nigdy bez reinitu. ``denorm_init`` instaluje TYLKO
triggery (na podstawie realnych modeli, gdzie ``wydzial`` jest już denorm-em);
wartości ustawia remap z kroku 2.
"""

from collections import defaultdict

import django.db.models.deletion
from django.core.management import call_command
from django.db import migrations, models


def drop_denorm_triggers(apps, schema_editor):
    """Zdejmij WSZYSTKIE triggery denorm przed retargetem kolumny."""
    call_command("denorm_drop")


def init_denorm_triggers(apps, schema_editor):
    """Zainstaluj triggery denorm na podstawie realnych modeli (``wydzial``
    jest już self-FK denorm). Instaluje TYLKO triggery — wartości dał remap."""
    call_command("denorm_init")


def _find_root(node_id, parent_map):
    """Korzeń drzewa dla ``node_id`` — wędrówka po ``parent_map`` (id→parent_id)
    do węzła bez rodzica. Guard na cykl (nie powinien wystąpić w drzewie)."""
    seen = set()
    current = node_id
    while True:
        parent_id = parent_map.get(current)
        if parent_id is None:
            return current
        if parent_id in seen:
            # Zabezpieczenie przed cyklem — zwróć bieżący jako „korzeń".
            return current
        seen.add(current)
        current = parent_id


def remap_wydzial_to_root(apps, schema_editor):
    """Ustaw ``wydzial_id`` = pk korzenia drzewa (NULL dla top-level).
    Idempotentne: przeliczane z aktualnego ``parent``."""
    Jednostka = apps.get_model("bpp", "Jednostka")

    parent_map = dict(Jednostka.objects.values_list("id", "parent_id"))

    roots = []
    by_root = defaultdict(list)
    for node_id, parent_id in parent_map.items():
        if parent_id is None:
            roots.append(node_id)
        else:
            by_root[_find_root(node_id, parent_map)].append(node_id)

    if roots:
        Jednostka.objects.filter(pk__in=roots).update(wydzial=None)
    for root_id, node_ids in by_root.items():
        Jednostka.objects.filter(pk__in=node_ids).update(wydzial=root_id)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0458_faza_b_ii1_views"),
    ]

    operations = [
        migrations.RunPython(drop_denorm_triggers, migrations.RunPython.noop),
        # Krok 1: FK→Wydzial → IntegerField (kolumna zostaje ``wydzial_id``).
        migrations.AlterField(
            model_name="jednostka",
            name="wydzial",
            field=models.IntegerField(blank=True, null=True, db_column="wydzial_id"),
        ),
        # Krok 2: policz korzeń wędrówką po ``parent``.
        migrations.RunPython(remap_wydzial_to_root, migrations.RunPython.noop),
        # Krok 3: IntegerField → self-FK (zamrożona postać denorm-a).
        migrations.AlterField(
            model_name="jednostka",
            name="wydzial",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="bpp.jednostka",
                verbose_name="Wydział",
            ),
        ),
        migrations.RunPython(init_denorm_triggers, migrations.RunPython.noop),
    ]
