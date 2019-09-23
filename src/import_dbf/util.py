import os

from dbfread import DBF

from .codecs import custom_search_function  # noqa

custom_search_function  # noqa


def addslashes(v):
    if not v:
        return v
    if not hasattr(v, 'replace'):
        return v
    return v.replace("'", "''")


def import_dbf(filename, appname="import_dbf"):
    tablename = appname + "_" + os.path.basename(filename.split(".")[0]).lower()
    dbf = DBF(filename, encoding="my_cp1250")

    print("DROP TABLE IF EXISTS %s;" % tablename)
    print("CREATE TABLE %s(" % tablename)
    for field in dbf.fields:
        print("\t%s text," % field.name.lower())
    print("\t_ignore_me text);")

    for record in dbf:
        print("INSERT INTO %s(%s) VALUES(%s);" % (tablename, ", ".join([f.lower() for f in record]),
                                                  ", ".join(["'%s'" % addslashes(v or '') for v in record.values()])))
