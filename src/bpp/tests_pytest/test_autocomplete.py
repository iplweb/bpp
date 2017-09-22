# -*- encoding: utf-8 -*-


import pytest

VALUES = [
    "Zi%C4%99ba+%5C",
    "Zi%C4%99ba+%5C \\",
    "fa\\\"fa",
    "'",
    "fa ' fa",
    " ' fa",
    " fa '",
    "fa\\'fa",
    "Zięba \\",
    "Test ; test",
    "test & test",
    "test &",
    "& test",
    "; test",
    "test ;",
    ":*",
    ":",
    ":* :* *: *:",
    "",
    "\\",
    "123 \\ 123",
    "\\ 123",
    "123 \\",
]
AUTOCOMPLETES = ["Autor", "Jednostka"]

@pytest.mark.django_db
@pytest.mark.parametrize("autocomplete_name", AUTOCOMPLETES)
@pytest.mark.parametrize("qstr", VALUES)
def test_autocomplete_bug_1(autocomplete_name, qstr, client):
    client.get(
        "/multiseek/autocomplete/%s/" % autocomplete_name,
        data={'qstr': qstr})

#
# @pytest.mark.django_db
# @pytest.mark.parametrize("autocomplete_name", AUTOCOMPLETES)
# @pytest.mark.parametrize("qstr", VALUES)
# def test_autocomplete_bug_2(autocomplete_name, qstr, browser, live_server):
#     """Kiedys taki URL wywoływał BUGa"""
#     browser.visit(live_server + "/multiseek/autocomplete/%(autocomplete_name)s/?term=%(qstr)s" % dict(
#         autocomplete_name=autocomplete_name, qstr=qstr))
#     assert "server error" not in browser.html.lower()
