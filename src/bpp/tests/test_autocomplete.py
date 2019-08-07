# -*- encoding: utf-8 -*-
import json

import pytest
from django.urls import reverse
from model_mommy import mommy

from bpp.models import Autor_Dyscyplina
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
    "bpp:dyscyplina-autocomplete",
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


def test_dyscyplina_naukowa_przypisanie_autocomplete(app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok):
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"))
    assert res.json['results'][0]['text'] == 'Podaj autora'

    f = json.dumps({'autor': autor_jan_kowalski.id})
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {'forward': f})
    assert res.json['results'][0]['text'] == 'Podaj rok'

    f = json.dumps({'autor': autor_jan_kowalski.id, "rok": "fa"})
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {'forward': f})
    assert res.json['results'][0]['text'] == 'Nieprawidłowy rok'

    f = json.dumps({'autor': autor_jan_kowalski.id, "rok": -10})
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {'forward': f})
    assert res.json['results'][0]['text'] == 'Nieprawidłowy rok'

    f = json.dumps({'autor': autor_jan_kowalski.id, "rok": rok})
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {'forward': f})
    assert res.json['results'][0]['text'] == 'Brak przypisania dla roku %i' % rok

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina2,
        subdyscyplina_naukowa=dyscyplina1
    )

    f = json.dumps({'autor': autor_jan_kowalski.id, "rok": rok})
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {'forward': f})
    assert res.json['results'][0]['text'] == 'druga dyscyplina'

    f = json.dumps({'autor': autor_jan_kowalski.id, "rok": rok})
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {'forward': f, 'q': 'memetyka'})
    assert res.json['results'][0]['text'] == 'memetyka stosowana'


def test_dyscyplina_naukowa_przypisanie_autocomplete_brak_drugiej(app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok):


    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina2,
    )

    f = json.dumps({'autor': autor_jan_kowalski.id, "rok": rok})
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {'forward': f})
    assert res.json['results'][0]['text'] == 'druga dyscyplina'


def test_wydawca_autocomplete(admin_client):
    res = admin_client.get(reverse("bpp:wydawca-autocomplete"))
    assert res.status_code == 200
