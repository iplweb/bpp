"""Bramka WHEN (lista kolumn) na UPDATE triggerach cache.

Spec: docs/deweloper/spec-bpp-refresh-cache-plpgsql-2026-06.md (Zmiana 2).

INSERT/DELETE zostaja bezwarunkowe (z 0432). UPDATE dostaje
``WHEN (OLD.col IS DISTINCT FROM NEW.col OR ...)`` gdzie lista = kolumny bazowe
faktycznie zasilajace wyjscie widoku(-ow) danej tabeli. Trigger nie wchodzi, gdy
zaden istotny atrybut sie nie zmienil (jalowy churn -- np. wsadowe zapisy
opl_pub_* nie bumpujace auto_now).

Lista kolumn idzie z pg_depend (poziom kolumn, regula _RETURN), NIE z dopasowania
nazw -- widok przemianowuje kolumny (wydawca_opis -> wydawnictwo w
zwarte/doktorat/habilitacja), wiec dopasowanie po nazwie gubiloby zrodlo i dawalo
cichy staleness. Odejmujemy {id, search_index, tytul_oryginalny_sort} (klucz;
pochodne, ktorych zrodla i tak sa w zbiorze). Doktorat/habilitacja: ∪ kolumny
zasilajace widok *_autorzy (autor_id, jednostka_id) -- bo autor lezy na wierszu
publikacji.

Kolejnosc termow OR: tanie/staloszerokie typy najpierw (short-circuit), drogie
(tekst/varchar/tablice/tsvector) na koniec.

Funkcje triggera sie NIE zmieniaja (to 0432) -- bramka siedzi na definicji
triggera, nie w ciele funkcji.
"""

from django.db import connection, migrations

# tabela -> (funkcja refresh, [widoki ktore tabela zasila])
GATED = [
    (
        "bpp_wydawnictwo_ciagle",
        "bpp_refresh_rekord_wydawnictwo_ciagle",
        ["bpp_wydawnictwo_ciagle_view"],
    ),
    (
        "bpp_wydawnictwo_zwarte",
        "bpp_refresh_rekord_wydawnictwo_zwarte",
        ["bpp_wydawnictwo_zwarte_view"],
    ),
    (
        "bpp_patent",
        "bpp_refresh_rekord_patent",
        ["bpp_patent_view"],
    ),
    (
        "bpp_praca_doktorska",
        "bpp_refresh_rekord_praca_doktorska",
        ["bpp_praca_doktorska_view", "bpp_praca_doktorska_autorzy"],
    ),
    (
        "bpp_praca_habilitacyjna",
        "bpp_refresh_rekord_praca_habilitacyjna",
        ["bpp_praca_habilitacyjna_view", "bpp_praca_habilitacyjna_autorzy"],
    ),
    (
        "bpp_wydawnictwo_ciagle_autor",
        "bpp_refresh_autor_wydawnictwo_ciagle",
        ["bpp_wydawnictwo_ciagle_autorzy"],
    ),
    (
        "bpp_wydawnictwo_zwarte_autor",
        "bpp_refresh_autor_wydawnictwo_zwarte",
        ["bpp_wydawnictwo_zwarte_autorzy"],
    ),
    (
        "bpp_patent_autor",
        "bpp_refresh_autor_patent",
        ["bpp_patent_autorzy"],
    ),
]

EXCLUDED = ("id", "search_index", "tytul_oryginalny_sort")


def _gate_columns(cur, table, views):
    """Kolumny bazowe ``table`` referowane przez ``views`` (pg_depend, poziom
    kolumn), bez {id, search_index, tytul_oryginalny_sort}, posortowane
    tanie-typy-pierwsze, potem attnum."""
    cur.execute(
        """
        SELECT a.attname
        FROM (
            SELECT DISTINCT a.attname, a.attnum,
                   (t.typcategory IN ('S','A')
                    OR a.atttypid = 'pg_catalog.tsvector'::regtype)::int AS expensive
            FROM pg_depend d
            JOIN pg_rewrite r ON r.oid = d.objid
            JOIN pg_class   v ON v.oid = r.ev_class AND v.relname = ANY(%s)
            JOIN pg_attribute a ON a.attrelid = d.refobjid
                                AND a.attnum = d.refobjsubid
            JOIN pg_type    t ON t.oid = a.atttypid
            WHERE d.refobjid = %s::regclass
              AND d.classid = 'pg_rewrite'::regclass
              AND d.refclassid = 'pg_class'::regclass
              AND d.refobjsubid > 0
              AND a.attname <> ALL(%s)
        ) a
        ORDER BY a.expensive, a.attnum
        """,
        [list(views), table, list(EXCLUDED)],
    )
    return [r[0] for r in cur.fetchall()]


def _when_clause(columns):
    return " OR ".join(f'OLD."{c}" IS DISTINCT FROM NEW."{c}"' for c in columns)


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        for table, refresh_fn, views in GATED:
            columns = _gate_columns(cur, table, views)
            if not columns:
                raise RuntimeError(
                    f"bramka dla {table}: pg_depend nie zwrocil zadnej kolumny "
                    f"(widoki={views}) -- nie tworze niezbramkowanego UPDATE"
                )
            when = _when_clause(columns)
            cur.execute(f"DROP TRIGGER IF EXISTS {table}_cache_upd ON {table};")
            cur.execute(
                f"CREATE TRIGGER {table}_cache_upd AFTER UPDATE ON {table} "
                f"FOR EACH ROW WHEN ({when}) "
                f"EXECUTE PROCEDURE {refresh_fn}();"
            )


def backward(apps, schema_editor):
    # Z powrotem do bezwarunkowego UPDATE (stan po 0432).
    with connection.cursor() as cur:
        for table, refresh_fn, _views in GATED:
            cur.execute(f"DROP TRIGGER IF EXISTS {table}_cache_upd ON {table};")
            cur.execute(
                f"CREATE TRIGGER {table}_cache_upd AFTER UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE PROCEDURE {refresh_fn}();"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0432_cache_trigger_plpgsql"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
