# -*- encoding: utf-8 -*-


import pytest
from django.urls import reverse
from model_mommy import mommy

from bpp.models.konferencja import Konferencja
from bpp.views.autocomplete import AdminNavigationAutocomplete, PublicAutorAutocomplete

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
    "test (test)",
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
    "|K"
]
AUTOCOMPLETES = [
    "bpp:public-autor-autocomplete",
    "bpp:jednostka-widoczna-autocomplete",
    "bpp:dyscyplina-autocomplete"
]

@pytest.mark.django_db
@pytest.mark.parametrize("autocomplete_name", AUTOCOMPLETES)
@pytest.mark.parametrize("qstr", VALUES)
def test_autocomplete_bug_1(autocomplete_name, qstr, client):
    res = client.get(
        reverse(autocomplete_name),
        data={'q': qstr})
    assert res.status_code == 200


@pytest.mark.django_db
def test_admin_konferencje():
    "Upewnij się, że konferencje wyskakują w AdminAutoComplete"
    k = mommy.make(Konferencja, nazwa="test 54")
    a = AdminNavigationAutocomplete()
    a.q = "test 54"
    assert k in a.get_queryset()


@pytest.mark.django_db
def test_public_autor_autocomplete_bug_1():
    a = PublicAutorAutocomplete()
    a.q = "a (b)"
    assert list(a.get_queryset()) is not None

    a.q = "a\tb"
    assert list(a.get_queryset()) is not None
