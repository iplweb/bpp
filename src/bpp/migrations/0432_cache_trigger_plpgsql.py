"""Port bpp_refresh_cache PL/Python -> statyczny PL/pgSQL.

Spec: docs/deweloper/spec-bpp-refresh-cache-plpgsql-2026-06.md (Zmiana 1).

Zamiast JEDNEJ dynamicznej funkcji PL/Python (introspekcja kolumn na KAZDYM
odpaleniu) generujemy per-tabela statyczne funkcje PL/pgSQL z wklejonymi na
sztywno listami kolumn. Introspekcja idzie z hot-path do migrate-path; runtime
dostaje SQL z cache'owanym planem.

8 funkcji refresh (5 rekord + 3 through) + 8 funkcji delete. Triggery sa
rozbite na INSERT / DELETE / UPDATE (UPDATE jeszcze bezwarunkowy -- bramka WHEN
to migracja 0433).

Zachowana DOKLADNIE semantyka v3 (0429):
- through-table odswieza tylko JEDEN wiersz autora (object_id_raw + autor_id);
- doktorat/habilitacja: DELETE + INSERT na bpp_autorzy_mat (widok *_autorzy ma
  INNER JOIN do bpp_autor -- wiersz moze wypasc ze zrodla);
- DELETE to OSOBNA funkcja (NEW jest NULL na DELETE -> upsert by nic nie
  skasowal); kasuje po id = ARRAY[ct, OLD.id];
- advisory lock przez SELECT ... INTO STRICT (pg_advisory_xact_lock jest STRICT;
  goly podselect z NULL cicho nie zablokowalby -- #309);
- mapowanie kolumn POZYCYJNE (widok *_autorzy nazywa kolumne-tablice 'array' lub
  'id' niespojnie; INSERT(mat) SELECT(widok) zgadza sie po kolejnosci).
"""

from pathlib import Path

from django.db import connection, migrations

# (tabela bazowa, model content_type, czy autor lezy na wierszu publikacji)
REKORD_SITES = [
    ("bpp_wydawnictwo_ciagle", "wydawnictwo_ciagle", False),
    ("bpp_wydawnictwo_zwarte", "wydawnictwo_zwarte", False),
    ("bpp_patent", "patent", False),
    ("bpp_praca_doktorska", "praca_doktorska", True),
    ("bpp_praca_habilitacyjna", "praca_habilitacyjna", True),
]

# (tabela through *_autor, model content_type publikacji)
THROUGH_SITES = [
    ("bpp_wydawnictwo_ciagle_autor", "wydawnictwo_ciagle"),
    ("bpp_wydawnictwo_zwarte_autor", "wydawnictwo_zwarte"),
    ("bpp_patent_autor", "patent"),
]

# Stare zlaczone triggery (v3 / 0400) do usuniecia.
OLD_TRIGGERS = [
    ("bpp_wydawnictwo_ciagle", "bpp_wydawnictwo_ciagle_cache_trigger"),
    ("bpp_wydawnictwo_ciagle_autor", "bpp_wydawnictwo_ciagle_autor_cache_trigger"),
    ("bpp_wydawnictwo_zwarte", "bpp_wydawnictwo_zwarte_cache_trigger"),
    ("bpp_wydawnictwo_zwarte_autor", "bpp_wydawnictwo_zwarte_autor_cache_trigger"),
    ("bpp_patent", "bpp_patent_cache_trigger"),
    ("bpp_patent_autor", "bpp_patent_autor_cache_trigger"),
    ("bpp_praca_doktorska", "bpp_praca_doktorska_cache_trigger"),
    ("bpp_praca_habilitacyjna", "bpp_praca_habilitacyjna_cache_trigger"),
]


def _q(c):
    return '"' + c + '"'


def _cols(cur, relname):
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        [relname],
    )
    return [r[0] for r in cur.fetchall()]


def _upsert_sql(cur, mat_table, source_view, source_where):
    """INSERT(mat_cols) SELECT(view_cols bez object_id_raw) ON CONFLICT (id)
    DO UPDATE SET. Mapowanie POZYCYJNE (patrz docstring modulu)."""
    mat_cols = _cols(cur, mat_table)
    src_cols = [c for c in _cols(cur, source_view) if c != "object_id_raw"]
    set_clause = ", ".join(f"{_q(c)} = EXCLUDED.{_q(c)}" for c in mat_cols if c != "id")
    return (
        f"INSERT INTO {mat_table} ({', '.join(_q(c) for c in mat_cols)})\n"
        f"      SELECT {', '.join(_q(c) for c in src_cols)} FROM {source_view}\n"
        f"      WHERE {source_where}\n"
        f"      ON CONFLICT (id) DO UPDATE SET {set_clause}"
    )


def _ct_lookup(model):
    # SELECT ... INTO STRICT -> glosny NO_DATA_FOUND zamiast cichego no-op locka.
    return (
        "SELECT id INTO STRICT ct FROM django_content_type "
        f"WHERE app_label='bpp' AND model='{model}';"
    )


def _create_rekord_function(cur, table, model, autor_na_wierszu):
    autorzy_view = table + "_autorzy"
    body_autorzy = ""
    if autor_na_wierszu:
        upsert_autorzy = _upsert_sql(
            cur, "bpp_autorzy_mat", autorzy_view, "object_id_raw = NEW.id"
        )
        body_autorzy = (
            "\n      DELETE FROM bpp_autorzy_mat "
            "WHERE rekord_id = ARRAY[ct, NEW.id]::integer[];\n"
            f"      {upsert_autorzy};"
        )
    upsert_rekord = _upsert_sql(
        cur, "bpp_rekord_mat", table + "_view", "object_id_raw = NEW.id"
    )
    return f"""
CREATE OR REPLACE FUNCTION bpp_refresh_rekord_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, NEW.id);
      {upsert_rekord};{body_autorzy}
      RETURN NULL;
END $bpp_body$;
"""


def _create_delete_rekord_function(model):
    return f"""
CREATE OR REPLACE FUNCTION bpp_delete_rekord_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, OLD.id);
      DELETE FROM bpp_rekord_mat WHERE id = ARRAY[ct, OLD.id]::integer[];
      RETURN NULL;
END $bpp_body$;
"""


def _create_through_function(cur, table, model):
    autorzy_view = table[: -len("_autor")] + "_autorzy"
    upsert = _upsert_sql(
        cur,
        "bpp_autorzy_mat",
        autorzy_view,
        "object_id_raw = NEW.rekord_id AND autor_id = NEW.autor_id",
    )
    return f"""
CREATE OR REPLACE FUNCTION bpp_refresh_autor_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, NEW.rekord_id);
      {upsert};
      RETURN NULL;
END $bpp_body$;
"""


def _create_delete_through_function(model):
    return f"""
CREATE OR REPLACE FUNCTION bpp_delete_autor_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, OLD.rekord_id);
      DELETE FROM bpp_autorzy_mat WHERE id = ARRAY[ct, OLD.id]::integer[];
      RETURN NULL;
END $bpp_body$;
"""


def _triggers(table, refresh_fn, delete_fn):
    # INSERT / DELETE bezwarunkowe; UPDATE w 0432 jeszcze bezwarunkowy
    # (bramka WHEN dochodzi w 0433).
    return [
        f"DROP TRIGGER IF EXISTS {table}_cache_ins ON {table};",
        f"DROP TRIGGER IF EXISTS {table}_cache_del ON {table};",
        f"DROP TRIGGER IF EXISTS {table}_cache_upd ON {table};",
        f"CREATE TRIGGER {table}_cache_ins AFTER INSERT ON {table} "
        f"FOR EACH ROW EXECUTE PROCEDURE {refresh_fn}();",
        f"CREATE TRIGGER {table}_cache_del AFTER DELETE ON {table} "
        f"FOR EACH ROW EXECUTE PROCEDURE {delete_fn}();",
        f"CREATE TRIGGER {table}_cache_upd AFTER UPDATE ON {table} "
        f"FOR EACH ROW EXECUTE PROCEDURE {refresh_fn}();",
    ]


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        # 1) Usun stare zlaczone triggery PL/Python.
        for table, trig in OLD_TRIGGERS:
            cur.execute(f"DROP TRIGGER IF EXISTS {trig} ON {table};")

        stmts = []
        # 2) Funkcje + triggery rekord.
        for table, model, autor_na_wierszu in REKORD_SITES:
            stmts.append(_create_rekord_function(cur, table, model, autor_na_wierszu))
            stmts.append(_create_delete_rekord_function(model))
            stmts += _triggers(
                table,
                f"bpp_refresh_rekord_{model}",
                f"bpp_delete_rekord_{model}",
            )
        # 3) Funkcje + triggery through.
        for table, model in THROUGH_SITES:
            stmts.append(_create_through_function(cur, table, model))
            stmts.append(_create_delete_through_function(model))
            stmts += _triggers(
                table,
                f"bpp_refresh_autor_{model}",
                f"bpp_delete_autor_{model}",
            )

        for s in stmts:
            cur.execute(s)

        # 4) Stara dynamiczna funkcja PL/Python jest juz nieuzywana (zaden
        #    trigger jej nie wola). Usuwamy ja -- to 9. (ostatnia w tym
        #    porcie) funkcja plpython3u; reszta + DROP EXTENSION to osobny
        #    spec (pozegnanie-z-plpython).
        cur.execute("DROP FUNCTION IF EXISTS bpp_refresh_cache();")


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        # 1) Usun nowe rozbite triggery + funkcje PL/pgSQL.
        for table, _model, _x in REKORD_SITES:
            for suffix in ("ins", "del", "upd"):
                cur.execute(
                    f"DROP TRIGGER IF EXISTS {table}_cache_{suffix} ON {table};"
                )
        for table, _model in THROUGH_SITES:
            for suffix in ("ins", "del", "upd"):
                cur.execute(
                    f"DROP TRIGGER IF EXISTS {table}_cache_{suffix} ON {table};"
                )
        for _table, model, _x in REKORD_SITES:
            cur.execute(f"DROP FUNCTION IF EXISTS bpp_refresh_rekord_{model}();")
            cur.execute(f"DROP FUNCTION IF EXISTS bpp_delete_rekord_{model}();")
        for _table, model in THROUGH_SITES:
            cur.execute(f"DROP FUNCTION IF EXISTS bpp_refresh_autor_{model}();")
            cur.execute(f"DROP FUNCTION IF EXISTS bpp_delete_autor_{model}();")

        # 2) Odtworz funkcje PL/Python v3 (0429) i zlaczone triggery (0400).
        for fname in ("0429_cache_trigger_v3.sql", "0400_restore_cache_triggers.sql"):
            sql = (Path(__file__).parent / fname).read_text()
            cur.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0431_search_index_gin"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
