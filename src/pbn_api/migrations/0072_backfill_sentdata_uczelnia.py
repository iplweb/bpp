"""Backfill SentData.uczelnia dla instalacji jednouczelnianych (Track 4).

FK ``SentData.uczelnia`` istnieje już (nullable) od migracji 0069 — TU NIE MA
zmiany schematu, tylko data-migration.

Polityka backfillu:

- Dokładnie 1 ``Uczelnia`` w bazie → wszystkie wiersze ``SentData`` z
  ``uczelnia IS NULL`` dostają tę uczelnię. Po tym single-install ma w 100%
  otagowane wiersze, a nowy keyed-lookup (``get_for_rec(rec, uczelnia)``) jest
  no-op względem starego globalnego zachowania.

- Multi-install (≥2 uczelnie) z wierszami NULL → NIE failujemy, NIE kasujemy,
  zostawiamy NULL. Nowy lookup filtruje po ``uczelnia``, więc wiersze NULL stają
  się niewidoczne dla keyed-lookup — kolejna wysyłka utworzy poprawnie otagowany
  wiersz. Koszt: co najwyżej jeden redundantny re-send per ``(rec, uczelnia)``
  (self-healing; PBN przyjmuje idempotentnie). Bezpieczne.

- 0 uczelni → nic do zrobienia (brak danych referencyjnych).

``uczelnia`` POZOSTAJE nullable (transitional; NULL = legacy/untagged).
Reverse migration to no-op (backfillu nie da się sensownie cofnąć — nie wiemy
które wiersze były wcześniej NULL).
"""

from django.db import migrations


def backfill_uczelnia(apps, schema_editor):
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    SentData = apps.get_model("pbn_api", "SentData")

    if Uczelnia.objects.count() == 1:
        jedyna = Uczelnia.objects.get()
        SentData.objects.filter(uczelnia__isnull=True).update(uczelnia=jedyna)
    # ≥2 uczelnie lub 0 — zostawiamy NULL (self-healing przy kolejnej wysyłce).


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_api", "0071_merge_0069_sentdata_api_url_0070_link_pbn_to_uczelnia"),
        ("bpp", "0414_copy_constance_to_uczelnia"),
    ]

    operations = [
        migrations.RunPython(backfill_uczelnia, migrations.RunPython.noop),
    ]
