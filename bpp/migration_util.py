# -*- encoding: utf-8 -*-


def load_custom_sql(mig_name, *args, **kw):
    import os
    from django.conf import settings
    from django.db import connection

    fn = os.path.join(os.path.dirname(__file__), 'migrations', mig_name + ".sql")
    #print "Loading %s... " % fn,
    data = open(fn, "rb").read().decode(settings.FILE_CHARSET)

    cursor = connection.cursor()
    cursor = cursor.cursor
    cursor.execute(data)
    #print "done!"
