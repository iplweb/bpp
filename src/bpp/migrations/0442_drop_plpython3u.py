from django.db import migrations


class Migration(migrations.Migration):
    """Pożegnanie z PL/Python — usuń rozszerzenie ``plpython3u``.

    Możliwe dopiero, gdy WSZYSTKIE funkcje plpython zostały przepisane na
    PL/pgSQL (0432 ``bpp_refresh_cache``, 0440 pozostałe 7) albo wyeliminowane
    (0441 ``trigger_tytul_sort``). Zależy od OBU liści grafu migracji
    (0433 z gałęzi cache-trigger, 0441 z gałęzi pożegnania z plpython), co
    jednocześnie scala równolegle zmergowane gałęzie w jeden liść.

    ``IF EXISTS``: świeże instalacje ładują baseline plython-free (rozszerzenia
    już nie ma) → no-op; istniejące/upgrade'owane bazy je mają → DROP.
    BEZ ``CASCADE``: gdyby cokolwiek nadal zależało od ``plpython3u``, migracja
    padnie głośno, zamiast po cichu usunąć zależne obiekty.
    """

    dependencies = [
        ("bpp", "0433_cache_trigger_when_gate"),
        ("bpp", "0441_drop_trigger_tytul_sort"),
    ]

    operations = [
        migrations.RunSQL(
            "DROP EXTENSION IF EXISTS plpython3u",
            reverse_sql="CREATE EXTENSION IF NOT EXISTS plpython3u",
        ),
    ]
