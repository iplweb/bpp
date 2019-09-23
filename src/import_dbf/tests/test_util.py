import os

from import_dbf.util import addslashes, import_dbf


def test_util_addslashes():
    assert addslashes(None) == None
    assert addslashes(1) == 1
    assert addslashes("foo'") == "foo''"


def test_util_import_dbf():
    import_dbf(os.path.join(os.path.dirname(__file__), "test.dbf"))
