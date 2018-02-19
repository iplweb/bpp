# -*- encoding: utf-8 -*-

import json

from pathlib import Path


def load_custom_sql(mig_name, *args, **kw):
    import os
    from django.conf import settings
    from django.db import connection

    fn = os.path.join(os.path.dirname(__file__), 'migrations', mig_name + ".sql")
    # print "Loading %s... " % fn,
    data = open(fn, "rb").read().decode(settings.FILE_CHARSET)

    cursor = connection.cursor()
    cursor = cursor.cursor
    cursor.execute(data)
    # print "done!"


def load_fixture_as_json(fixture_name):
    return json.loads(
        open(str(find_fixture_path(fixture_name)), "r").read()
    )


def find_fixture_path(fixture):
    return Path(__file__).parent / "fixtures" / (fixture + ".json")


def load_historic_fixture(apps, fixture_name, klass, app_name="bpp"):
    for elem in load_fixture_as_json(fixture_name):
        app_name, klass = elem['model'].split(".")
        klassobj = apps.get_model(app_name, klass)
        kw = elem['fields']
        kw["pk"] = elem['pk']
        klassobj.objects.create(**kw)
