# -*- encoding: utf-8 -*-

"""
Ten moduł zawiera hook do post_syncdb który utworzy grupy
dla wszystkich użytkowników.
"""

from __future__ import print_function
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.db.models.signals import post_syncdb
from django.db import transaction, connection
from django.contrib.auth.models import Group
from django.conf import settings

import bpp
import traceback

from bpp.system import groups
import os, sys

def bpp_post_syncdb(force=False, **kw):
    # Jeżeli grupy były już utworzone to ich nie twórz więcej
    if Group.objects.filter(name='administracja').count() != 0 and not force:
        print("Groups exists! Not creating them...")
        return

    #
    for name, models in groups.items():
        try:
            Group.objects.get(name=name).delete()
        except Group.DoesNotExist:
            pass
        # print "Creating group '%s'..." % name
        g = Group.objects.create(name=name)
        for model in models:
            content_type = ContentType.objects.get_for_model(model)
            for permission in Permission.objects.filter(
                content_type=content_type):
                g.permissions.add(permission)

post_syncdb.connect(bpp_post_syncdb, bpp.models)


def load_customized_sql(app, created_models, verbosity=2, **kwargs):
    app_dir = os.path.normpath(
        os.path.join(os.path.dirname(app.__file__), 'sql'))
    custom_files = [
        #os.path.join(app_dir, "custom.%s.sql" % settings.DATABASE_ENGINE),
        os.path.join(app_dir, "custom.sql")]

    for custom_file in custom_files:
        if os.path.exists(custom_file):
            print("Loading %s" % custom_file)
            fp = open(custom_file, 'U')
            cursor = connection.cursor()
            buf = fp.read().decode(settings.FILE_CHARSET)

            # Jest coś spsute z Django, w taki sposob się to objawia -- jakby
            # w zależności od ustawień on chciał coś formatować:
            # if sys.platform != 'linux2':
            #     if not settings.TESTING:
            #         buf = buf.replace("%", "%%")
            # else:
            #     if not settings.TESTING:
            #         buf = buf.replace("%", "%%")
                
            try:
                cursor.execute(buf)
            except Exception, e:
                try:
                    cursor.execute(buf.replace("%", "%%"))
                except Exception, e:
                    sys.stderr.write(
                        "Couldn't execute custom SQL for %s" % app.__name__)

                    traceback.print_exc()
                    transaction.rollback_unless_managed()
            else:
                transaction.commit_unless_managed()


post_syncdb.connect(load_customized_sql, bpp.models)