from django.db import migrations

from bpp.migration_util import load_custom_sql


class Migration(migrations.Migration):
    """Usuń kolację libc ``public."pl_PL"`` i klauzule ``COLLATE`` z widoków.

    Kolacja (``0001_collation.sql``: ``CREATE COLLATION "pl_PL"
    locale='pl_PL.UTF-8'``) to kolacja libc, której stockowy/oficjalny obraz
    ``postgres`` NIE potrafi dostarczyć (generuje tylko ``en_US.UTF-8``).
    Projekt migruje z własnego ``iplweb/bpp_dbserver`` na stockowego
    postgresa, więc kolacja musi zniknąć.

    Była używana WYŁĄCZNIE na stałych literałach ASCII w 5 widokach
    ``bpp_kronika_*_view`` (no-op dla sortowania). Forward (sidecar
    ``.sql``): ``CREATE OR REPLACE VIEW`` dla 5 widoków BEZ ``COLLATE``, a
    potem ``DROP COLLATION IF EXISTS public."pl_PL"``.

    Idempotencja: ``CREATE OR REPLACE VIEW`` + ``DROP COLLATION IF EXISTS``
    są bezpieczne i na świeżych instalacjach z (zedytowanego) baseline (brak
    kolacji → no-op), i na istniejących klastrach ze starego obrazu (kolacja
    obecna → DROP po skasowaniu zależnych widoków). BEZ ``CASCADE`` — gdyby
    coś jeszcze zależało od kolacji, migracja padnie głośno.

    Reverse (sidecar ``..._reverse.sql``): odtwarza kolację i 5 widoków z
    ``COLLATE`` — działa TYLKO na obrazie z locale libc ``pl_PL.UTF-8``.

    Zależy od ``0442_drop_plpython3u`` (liść grafu migracji bpp na dysku).
    """

    dependencies = [
        ("bpp", "0442_drop_plpython3u"),
    ]

    operations = [
        migrations.RunPython(
            lambda *args, **kw: load_custom_sql("0443_drop_pl_PL_collation"),
            lambda *args, **kw: load_custom_sql("0443_drop_pl_PL_collation_reverse"),
        ),
    ]
