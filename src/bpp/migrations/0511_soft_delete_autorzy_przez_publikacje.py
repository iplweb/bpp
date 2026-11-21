"""Autorstwa publikacji z kosza znikają z ``bpp_autorzy_mat`` (i wracają).

Tabele łączące ``*_autor`` NIE mają własnego kosza (decyzja właściciela,
listopad 2026) — wiersz autorstwa „znika" razem z publikacją. Ta migracja
robi to samo po stronie SQL dla trzech typów z through-modelem
(``wydawnictwo_ciagle``, ``wydawnictwo_zwarte``, ``patent``). Doktoraty
i habilitacje (autor na wierszu publikacji) obsłużyła już ``0510``.

Trzy kroki:

1) widoki ``bpp_<typ>_autorzy`` dostają ``WHERE EXISTS`` na żywą publikację
   (``deleted_at IS NULL``). To one karmią ``bpp_autorzy_mat`` — zarówno
   z triggera, jak i przy pełnej przebudowie. Semi-join po kluczu głównym
   publikacji: na hot-pathie triggera (``object_id_raw = X AND autor_id = Y``)
   dokłada jedną sondę po pkey;
2) funkcja ``bpp_refresh_rekord_<typ>()`` (trigger UPDATE/INSERT tabeli
   publikacji) dostaje dwie gałęzie:

   - publikacja poszła do kosza -> ``DELETE FROM bpp_autorzy_mat`` dla
     wszystkich jej autorstw (obok ``bpp_rekord_mat``, które kasuje już
     ``0510``);
   - publikacja wróciła z kosza (``OLD.deleted_at IS NOT NULL``) -> upsert
     jej autorstw z widoku z kroku 1.

   Zwykła edycja publikacji (``deleted_at`` bez zmian) NIE dotyka
   ``bpp_autorzy_mat`` — koszt triggera się nie zmienia;
3) bramki WHEN nie trzeba regenerować: ``deleted_at`` tabeli publikacji jest
   w bramce od ``0510`` (widok ``bpp_<typ>_view``), a kolumny tabel
   ``*_autor`` referowane przez widoki ``*_autorzy`` się nie zmieniają.

Definicje są generowane z introspekcji (jak w ``0432``/``0433``/``0510``),
a nie przepisane do ``.sql`` — kopia rozjechałaby się przy najbliższej
zmianie kolumn.
"""

import importlib

from django.db import connection, migrations

_p0432 = importlib.import_module("bpp.migrations.0432_cache_trigger_plpgsql")
_p0510 = importlib.import_module("bpp.migrations.0510_soft_delete_rekord_views")

#: (tabela publikacji, model content_type, tabela through, widok autorzy)
SITES = [
    (
        "bpp_wydawnictwo_ciagle",
        "wydawnictwo_ciagle",
        "bpp_wydawnictwo_ciagle_autor",
        "bpp_wydawnictwo_ciagle_autorzy",
    ),
    (
        "bpp_wydawnictwo_zwarte",
        "wydawnictwo_zwarte",
        "bpp_wydawnictwo_zwarte_autor",
        "bpp_wydawnictwo_zwarte_autorzy",
    ),
    ("bpp_patent", "patent", "bpp_patent_autor", "bpp_patent_autorzy"),
]

#: Początek wstawki rozpoznawany przy cofaniu (format pg_get_viewdef
#: pretty=true: klauzula główna na wcięciu dwóch spacji).
MARKER = "\n  WHERE (EXISTS ("


def _viewdef(cur, widok):
    cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
    return cur.fetchone()[0].rstrip().rstrip(";")


def _predykat(tabela, through):
    return (
        f"EXISTS (SELECT 1 FROM {tabela} _pub "
        f"WHERE _pub.id = {through}.rekord_id AND _pub.deleted_at IS NULL)"
    )


def _filtruj_widok(cur, tabela, through, widok):
    orig = _viewdef(cur, widok)
    if MARKER in orig:
        return  # już przefiltrowany (idempotencja)
    if not orig.endswith(f"FROM {through}"):
        raise RuntimeError(
            f"{widok}: definicja nie kończy się na 'FROM {through}' — "
            f"dopisanie WHERE byłoby niepoprawne. Koniec definicji: "
            f"{orig[-160:]!r}"
        )
    cur.execute(
        f"CREATE OR REPLACE VIEW {widok} AS {orig}\n"
        f"  WHERE {_predykat(tabela, through)}"
    )


def _odfiltruj_widok(cur, widok):
    orig = _viewdef(cur, widok)
    if MARKER not in orig:
        return
    cur.execute(f"CREATE OR REPLACE VIEW {widok} AS {orig[: orig.rindex(MARKER)]}")


def _funkcja(cur, tabela, model, widok_autorzy):
    upsert_rekord = _p0432._upsert_sql(
        cur, "bpp_rekord_mat", tabela + "_view", "object_id_raw = NEW.id"
    )
    upsert_autorzy = _p0432._upsert_sql(
        cur, "bpp_autorzy_mat", widok_autorzy, "object_id_raw = NEW.id"
    )
    return f"""
CREATE OR REPLACE FUNCTION bpp_refresh_rekord_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_p0432._ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, NEW.id);
      IF NEW.deleted_at IS NOT NULL THEN
          DELETE FROM bpp_rekord_mat WHERE id = ARRAY[ct, NEW.id]::integer[];
          DELETE FROM bpp_autorzy_mat
              WHERE rekord_id = ARRAY[ct, NEW.id]::integer[];
          RETURN NULL;
      END IF;
      {upsert_rekord};
      IF TG_OP = 'UPDATE' AND OLD.deleted_at IS NOT NULL THEN
          {upsert_autorzy};
      END IF;
      RETURN NULL;
END $bpp_body$;
"""


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        for tabela, _model, through, widok in SITES:
            _filtruj_widok(cur, tabela, through, widok)
        for tabela, model, _through, widok in SITES:
            cur.execute(_funkcja(cur, tabela, model, widok))


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        for _tabela, _model, _through, widok in SITES:
            _odfiltruj_widok(cur, widok)
        for tabela, model, _through, _widok in SITES:
            cur.execute(_p0510._funkcja_z_galezia_kasujaca(cur, tabela, model, False))


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0510_soft_delete_rekord_views"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
