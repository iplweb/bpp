"""Backfill PublikacjaInstytucji_V2.uczelnia dla instalacji jednouczelnianych.

(Multi-hosted, audyt uczelnia, track 7b.)

FK ``PublikacjaInstytucji_V2.uczelnia`` istnieje już (nullable) od migracji
0069 — TU NIE MA zmiany schematu, tylko data-migration.

Polityka backfillu (mirror 0072_backfill_sentdata_uczelnia):

- Dokładnie 1 ``Uczelnia`` w bazie → wszystkie wiersze
  ``PublikacjaInstytucji_V2`` z ``uczelnia IS NULL`` dostają tę uczelnię.
  Po tym single-install ma w 100% otagowane wiersze, a nowy keyed-lookup
  (``link_do_pi(uczelnia)``) jest no-op względem starego globalnego zachowania.

- Multi-install (≥2 uczelnie) z wierszami NULL → NIE failujemy, NIE kasujemy,
  zostawiamy NULL. W przeciwieństwie do pozostałych luster danych PBN
  ``_V2`` NIE MA pola ``institutionId``, więc jedynym kluczem per-uczelni jest
  FK ``uczelnia`` — istniejących nieotagowanych wierszy NIE da się
  deterministycznie zmapować na uczelnię. Self-heal: write-side tag
  (``zapisz_publikacje_instytucji_v2``) otaguje wiersze przy kolejnym synchu,
  a ``update_or_create`` po ``(uuid, objectId)`` zaktualizuje istniejący wiersz
  in-place (NULL → uczelnia). Bezpieczne.

- 0 uczelni → nic do zrobienia (brak danych referencyjnych).

``uczelnia`` POZOSTAJE nullable (transitional; NULL = legacy/untagged).
Reverse migration to no-op (backfillu nie da się sensownie cofnąć — nie wiemy
które wiersze były wcześniej NULL).
"""

from django.db import migrations


def backfill_uczelnia(apps, schema_editor):
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    PublikacjaInstytucji_V2 = apps.get_model("pbn_api", "PublikacjaInstytucji_V2")

    if Uczelnia.objects.count() == 1:
        jedyna = Uczelnia.objects.get()
        PublikacjaInstytucji_V2.objects.filter(uczelnia__isnull=True).update(
            uczelnia=jedyna
        )
    # ≥2 uczelnie lub 0 — zostawiamy NULL (self-healing przy kolejnym synchu;
    # _V2 nie ma institutionId, więc nie ma jak zgadnąć uczelni).


class Migration(migrations.Migration):
    dependencies = [
        ("pbn_api", "0072_backfill_sentdata_uczelnia"),
        ("bpp", "0414_copy_constance_to_uczelnia"),
    ]

    operations = [
        migrations.RunPython(backfill_uczelnia, migrations.RunPython.noop),
    ]
