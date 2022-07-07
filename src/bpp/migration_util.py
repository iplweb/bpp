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
        qry = f"ALTER SEQUENCE { klassobj._meta.db_table }_id_seq RESTART WITH { cnt + 1 }"
        cur.execute(qry)
