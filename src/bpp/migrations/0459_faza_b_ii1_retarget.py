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

# Faza B (#438), F1: mapa CharField ``rodzaj_jednostki`` → nazwa ``RodzajJednostki``
# (identyczna z backfillem 0451). Jednostki utworzone w adminie MIĘDZY Fazą A a B
# mają ``rodzaj_jednostki`` ustawione, ale ``rodzaj`` (FK) NULL, bo 0451 objął
# tylko wiersze istniejące w chwili Fazy A. Re-backfill domyka to okno driftu,
# zanim FK-owa logika wykluczania kół (``ranking_autorow``) zacznie działać.
RODZAJ_CHARFIELD_MAPA = {"normalna": "Standard", "kolo_naukowe": "Koło naukowe"}


def rebackfill_rodzaj_z_charfield(apps, schema_editor):
    """Idempotentnie uzupełnij FK ``rodzaj`` z CharField ``rodzaj_jednostki``.

    Dotyka WYŁĄCZNIE wierszy z ``rodzaj_id IS NULL`` i niepustym CharField —
    więc bezpieczne przy wielokrotnym uruchomieniu (III-1 też re-backfilluje).
    """
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
        # ``init_denorm_triggers`` (denorm_init niżej) buduje triggery z
        # AKTUALNYCH modeli, więc WSZYSTKIE kolumny śledzone przez denorm muszą
        # już istnieć w bazie. Kolumny ``ukryty`` (typ_kbn/charakter_formalny/
        # charakter_pbn) dochodzą w równoległej gałęzi #405; bez tej krawędzi
        # sortowanie topologiczne po scaleniu na ``dev`` ustawiało je PO 0459 i
        # ``CREATE TRIGGER ... WHEN (OLD."ukryty" ...)`` wywalał migrację
        # (ProgrammingError: kolumna old.ukryty nie istnieje) na teście i prod.
        ("bpp", "0444_charakter_formalny_ukryty_charakter_pbn_ukryty_and_more"),
    ]

    operations = [
        # F1: domknij drift ``rodzaj_jednostki`` (CharField) → ``rodzaj`` (FK)
        # PRZED momentem, gdy FK-owe wykluczanie kół z rankingu wchodzi w życie.
        migrations.RunPython(rebackfill_rodzaj_z_charfield, migrations.RunPython.noop),
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
