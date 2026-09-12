import json
from collections import defaultdict
from pathlib import Path


def load_custom_sql(mig_name, app_name="bpp", charset="utf-8", *args, **kw):
    import os

    from django.db import connection

    fn = os.path.join(
        os.path.dirname(__file__), "..", app_name, "migrations", mig_name + ".sql"
    )
    # print "Loading %s... " % fn,
    data = open(fn, "rb").read().decode(charset)

    cursor = connection.cursor()
    cursor = cursor.cursor
    cursor.execute(data)
    # print "done!"


# Konstrukcje, przy których DOPISANIE `AND <warunek>` na koniec definicji
# widoku NIE jest równoważne dołożeniu warunku do WHERE:
# - " OR "   -> AND wiąże mocniej, więc `... OR x AND nowy` zmienia sens;
# - GROUP BY / HAVING / WINDOW / ORDER BY / LIMIT / OFFSET / UNION / ...
#              -> definicja nie kończy się na WHERE, więc `AND` wylądowałby
#                 w cudzej klauzuli (albo dał błąd składni).
_ZAKAZANE_W_WIDOKU = (
    " OR ",
    "GROUP BY",
    "HAVING",
    "WINDOW",
    "ORDER BY",
    "LIMIT",
    "OFFSET",
    "UNION",
    "INTERSECT",
    "EXCEPT",
)

# pg_get_viewdef(pretty=true) renderuje klauzulę WHERE najwyższego poziomu
# jako linię zaczynającą się od DWÓCH spacji; WHERE podzapytań jest wcięty
# głębiej. Liczba wystąpień tego wzorca odróżnia więc widok z jednym WHERE
# od widoku z UNION-em (gdzie dopisanie AND trafiłoby tylko w ostatnią gałąź).
_TOP_LEVEL_WHERE = "\n  WHERE "


def viewdef(cur, widok):
    """``pg_get_viewdef`` (pretty) bez końcowego średnika i białych znaków."""
    cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
    return cur.fetchone()[0].rstrip().rstrip(";")


def _sprawdz_ze_mozna_dopisac_and(widok, definicja):
    for zakazane in _ZAKAZANE_W_WIDOKU:
        if zakazane in definicja:
            raise RuntimeError(
                f"{widok}: definicja zawiera {zakazane!r} -- dopisanie "
                f"'AND <warunek>' na koncu nie byloby rownowazne dolozeniu "
                f"warunku do WHERE. Przepisz migracje recznie."
            )
    ile = definicja.count(_TOP_LEVEL_WHERE)
    if ile != 1:
        raise RuntimeError(
            f"{widok}: oczekiwano DOKLADNIE jednej klauzuli WHERE najwyzszego "
            f"poziomu, znaleziono {ile}. Definicja: ...{definicja[-160:]!r}"
        )


def widok_dopisz_warunek(cur, widok, warunek):
    """Dokłada ``AND <warunek>`` do WHERE istniejącego widoku.

    Wychodzi z INTROSPEKCJI (``pg_get_viewdef``), nie z tekstu migracji, która
    widok stworzyła — kopia SQL-a rozjechałaby się przy najbliższej zmianie
    kolumn. ``CREATE OR REPLACE VIEW`` zachowuje listę i typy kolumn, więc
    widoki zależne (np. ``bpp_nowe_sumy_view`` — UNION ALL po pięciu widokach)
    NIE są kasowane; nie ma tu żadnego ``DROP ... CASCADE``.

    Idempotentna: gdy warunek już jest w definicji, nie robi nic.
    """
    definicja = viewdef(cur, widok)
    if warunek in definicja:
        return
    _sprawdz_ze_mozna_dopisac_and(widok, definicja)
    cur.execute(f"CREATE OR REPLACE VIEW {widok} AS {definicja} AND {warunek}")


def widok_usun_warunek(cur, widok, warunek):
    """Odwrotność ``widok_dopisz_warunek`` (dla ``backward()``).

    Wycina DOKŁADNIE dopisany sufiks ``AND <warunek>``; gdy go nie ma — no-op
    (migracja cofana dwa razy albo widok w międzyczasie przebudowany).
    """
    definicja = viewdef(cur, widok)
    sufiks = f" AND {warunek}"
    if not definicja.endswith(sufiks):
        return
    cur.execute(f"CREATE OR REPLACE VIEW {widok} AS {definicja[: -len(sufiks)]}")


def load_fixture_as_json(fixture_name):
    return json.loads(open(str(find_fixture_path(fixture_name))).read())


def find_fixture_path(fixture):
    return Path(__file__).parent / "fixtures" / (fixture + ".json")


def load_historic_fixture(apps, fixture_name, klass, app_name="bpp"):
    max_id_map = defaultdict(int)
    for elem in load_fixture_as_json(fixture_name):
        app_name, klass = elem["model"].split(".")
        klassobj = apps.get_model(app_name, klass)
        kw = elem["fields"]
        pk = int(elem["pk"])
        kw["pk"] = pk
        max_id_map[klassobj] = max(max_id_map[klassobj], pk)
        klassobj.objects.create(**kw)

    from django.db import connection

    cur = connection.cursor()
    for klassobj, cnt in max_id_map.items():
        qry = f"ALTER SEQUENCE {klassobj._meta.db_table}_id_seq RESTART WITH {cnt + 1}"
        cur.execute(qry)
