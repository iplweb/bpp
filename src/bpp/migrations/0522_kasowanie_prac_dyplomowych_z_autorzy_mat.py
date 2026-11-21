"""Twarde skasowanie doktoratu/habilitacji czyści też ``bpp_autorzy_mat``.

``bpp_delete_rekord_<model>()`` (``0432``) usuwała wiersz wyłącznie
z ``bpp_rekord_mat``. Dla ``praca_doktorska``/``praca_habilitacyjna`` autor
leży na wierszu samej pracy — nie ma tabeli ``*_autor``, której trigger
sprzątnąłby ``bpp_autorzy_mat`` — więc po twardym skasowaniu zostawał tam
osierocony wiersz (np. ``Jednostka.wspolpracowali()`` dalej listował pracę).
Twarde kasowanie prac dyplomowych jest rzadkie (m.in. ponowny import z PBN),
ale sprzątać trzeba poprawnie.

NIEODWRACALNA (brak ``reverse_code``) — jak cały łańcuch soft-delete
``bpp/0511``–``0523``; powrót wyłącznie z kopii bazy.
"""

import importlib

from django.db import connection, migrations

_p0432 = importlib.import_module("bpp.migrations.0432_cache_trigger_plpgsql")

MODELE = ["praca_doktorska", "praca_habilitacyjna"]


def _funkcja(model):
    return f"""
CREATE OR REPLACE FUNCTION bpp_delete_rekord_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_p0432._ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, OLD.id);
      DELETE FROM bpp_rekord_mat WHERE id = ARRAY[ct, OLD.id]::integer[];
      DELETE FROM bpp_autorzy_mat WHERE rekord_id = ARRAY[ct, OLD.id]::integer[];
      RETURN NULL;
END $bpp_body$;
"""


def _sprzataj_osierocone(cur):
    """Jednorazowo: wiersze ``bpp_autorzy_mat`` po pracach już skasowanych."""
    for model in MODELE:
        cur.execute(
            f"""
            DELETE FROM bpp_autorzy_mat a
            USING django_content_type ct
            WHERE ct.app_label = 'bpp' AND ct.model = %s
              AND a.rekord_id[1] = ct.id
              AND NOT EXISTS (
                  SELECT 1 FROM bpp_{model} p WHERE p.id = a.rekord_id[2]
              )
            """,
            [model],
        )


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        for model in MODELE:
            cur.execute(_funkcja(model))
        _sprzataj_osierocone(cur)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0521_slug_unikalny_razem_z_koszem"),
    ]

    operations = [
        migrations.RunPython(forward),
    ]
