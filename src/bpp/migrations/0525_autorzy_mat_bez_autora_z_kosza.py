"""``bpp_autorzy_mat`` nigdy nie zawiera autora z kosza.

Warstwa Pythona pilnuje, żeby żywa publikacja nie wskazywała na autora
z kosza (guard kosza autora liczy tylko żywe prace, a ``restore()``
publikacji odmawia, gdy jej autor jest w koszu). Ta migracja to siatka
bezpieczeństwa w SQL, niezależna od ścieżki zapisu:

1. ``bpp_autorzy_mat_bez_autora_z_kosza`` — ``BEFORE INSERT`` na
   ``bpp_autorzy_mat``: wiersz autora z kosza nie jest wstawiany (każda
   ścieżka: triggery odświeżające, pełna przebudowa cache). Funkcje
   odświeżające robią ``INSERT … ON CONFLICT DO UPDATE``; ``BEFORE INSERT``
   leci przed sprawdzeniem konfliktu, więc istniejący wiersz o tym samym
   ``id`` (np. autorstwo przepięte na autora z kosza) jest kasowany,
   a nie zostawiany nieaktualny.
2. ``bpp_autor_kosz_autorzy_mat`` — ``AFTER UPDATE OF deleted_at`` na
   ``bpp_autor``: kosz autora kasuje jego wiersze z ``bpp_autorzy_mat``,
   przywrócenie odtwarza je z widoku ``bpp_autorzy`` (który i tak pomija
   publikacje z kosza).

Odwracalna (usuwa triggery i funkcje) — nie zmienia danych poza cache.
"""

import importlib

from django.db import connection, migrations

_p0432 = importlib.import_module("bpp.migrations.0432_cache_trigger_plpgsql")

FUNKCJA_MAT = """
CREATE OR REPLACE FUNCTION bpp_autorzy_mat_bez_autora_z_kosza() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
BEGIN
    IF NEW.autor_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM bpp_autor
        WHERE id = NEW.autor_id AND deleted_at IS NOT NULL
    ) THEN
        DELETE FROM bpp_autorzy_mat WHERE id = NEW.id;
        RETURN NULL;
    END IF;
    RETURN NEW;
END $bpp_body$;
"""

TRIGGER_MAT = """
DROP TRIGGER IF EXISTS bpp_autorzy_mat_bez_autora_z_kosza ON bpp_autorzy_mat;
CREATE TRIGGER bpp_autorzy_mat_bez_autora_z_kosza
    BEFORE INSERT ON bpp_autorzy_mat
    FOR EACH ROW EXECUTE FUNCTION bpp_autorzy_mat_bez_autora_z_kosza();
"""

TRIGGER_AUTOR = """
DROP TRIGGER IF EXISTS bpp_autor_kosz_autorzy_mat ON bpp_autor;
CREATE TRIGGER bpp_autor_kosz_autorzy_mat
    AFTER UPDATE OF deleted_at ON bpp_autor
    FOR EACH ROW WHEN (OLD.deleted_at IS DISTINCT FROM NEW.deleted_at)
    EXECUTE FUNCTION bpp_autor_kosz_autorzy_mat();
"""


def _funkcja_autor(cur):
    mat = _p0432._cols(cur, "bpp_autorzy_mat")
    zrodlo = _p0432._cols(cur, "bpp_autorzy")
    if len(mat) != len(zrodlo):
        # Mapowanie kolumn jest pozycyjne (jak w 0432) — inna liczba kolumn
        # oznacza, że widok i tabela się rozjechały.
        raise RuntimeError(
            f"bpp_autorzy ({zrodlo}) i bpp_autorzy_mat ({mat}) mają różne kolumny"
        )
    upsert = _p0432._upsert_sql(
        cur, "bpp_autorzy_mat", "bpp_autorzy", "autor_id = NEW.id"
    )
    return f"""
CREATE OR REPLACE FUNCTION bpp_autor_kosz_autorzy_mat() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
BEGIN
    IF NEW.deleted_at IS NOT NULL THEN
        DELETE FROM bpp_autorzy_mat WHERE autor_id = NEW.id;
    ELSE
        {upsert};
    END IF;
    RETURN NULL;
END $bpp_body$;
"""


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        cur.execute(FUNKCJA_MAT)
        cur.execute(TRIGGER_MAT)
        cur.execute(_funkcja_autor(cur))
        cur.execute(TRIGGER_AUTOR)
        # Jednorazowo: wiersze autorów, którzy już są w koszu.
        cur.execute(
            "DELETE FROM bpp_autorzy_mat m USING bpp_autor a "
            "WHERE m.autor_id = a.id AND a.deleted_at IS NOT NULL"
        )


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        cur.execute(
            "DROP TRIGGER IF EXISTS bpp_autor_kosz_autorzy_mat ON bpp_autor;"
            "DROP FUNCTION IF EXISTS bpp_autor_kosz_autorzy_mat();"
            "DROP TRIGGER IF EXISTS bpp_autorzy_mat_bez_autora_z_kosza "
            "ON bpp_autorzy_mat;"
            "DROP FUNCTION IF EXISTS bpp_autorzy_mat_bez_autora_z_kosza();"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0524_bppuser_jednostki_metryk"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
