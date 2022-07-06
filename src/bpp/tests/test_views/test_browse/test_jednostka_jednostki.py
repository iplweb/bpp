import random

import pytest

from bpp.tests import normalize_html

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from model_mommy import mommy

from fixtures import JEDNOSTKA_PODRZEDNA, JEDNOSTKA_UCZELNI

from bpp.models import Uczelnia
from bpp.models.autor import Autor
from bpp.views.browse import JednostkiView


@pytest.mark.django_db
def test_jednostka_nie_wyswietlaj_autorow_gdy_wielu(client, jednostka):
    for n in range(102):
        jednostka.dodaj_autora(mommy.make(Autor))

    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))
    assert "... napisane przez" not in res.rendered_content


def test_browse_jednostka_nadrzedna(jednostka, jednostka_podrzedna, client):
    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    page = client.get(url)
    assert "Jest nadrzędną jednostką dla" in normalize_html(page.rendered_content)

    url = reverse("bpp:browse_jednostka", args=(jednostka_podrzedna.slug,))
    page = client.get(url)
    assert "Wchodzi w skład" in normalize_html(page.rendered_content)


@pytest.mark.django_db
def test_browse_jednostka_paginate_by(uczelnia: Uczelnia):
    j = JednostkiView()
    assert j.get_paginate_by(None) == uczelnia.ilosc_jednostek_na_strone

    ile = random.randint(10, 10000)
    uczelnia.ilosc_jednostek_na_strone = ile
    uczelnia.save()
    assert j.get_paginate_by(None) == ile


def test_browse_jednostka_sortowanie(jednostka, jednostka_podrzedna, uczelnia, client):

    jednostka.nazwa = "Z jednostka"
    jednostka.save()

    jednostka_podrzedna.nazwa = "A jednostka"
    jednostka_podrzedna.save()

    uczelnia.sortuj_jednostki_alfabetycznie = True
    uczelnia.save()

    url = reverse("bpp:browse_jednostki")
    page = client.get(url)
    idx1 = page.rendered_content.find("A jednostka")
    idx2 = page.rendered_content.find("Z jednostka")

    assert idx1 < idx2

    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()
    page = client.get(url)

    idx1 = page.rendered_content.find("A jednostka")
    idx2 = page.rendered_content.find("Z jednostka")
    assert idx1 > idx2


def test_browse_jednostka_nadrzedna_tekst(jednostka_podrzedna, jednostka, client):
    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    res = client.get(url)
    assert "Jest nadrzędną jednostką dla" in normalize_html(res.rendered_content)

    url = reverse("bpp:browse_jednostka", args=(jednostka_podrzedna.slug,))
    res = client.get(url)
    assert "Jest nadrzędną jednostką dla" not in normalize_html(res.rendered_content)


def test_browse_pokazuj_tylko_jednostki_nadrzedne_nie(
    jednostka_podrzedna, jednostka, client, uczelnia
):
    url = reverse("bpp:browse_jednostki")
    res = client.get(url)
    assert JEDNOSTKA_UCZELNI in normalize_html(res.rendered_content)
    assert JEDNOSTKA_PODRZEDNA in normalize_html(res.rendered_content)


def test_browse_pokazuj_tylko_jednostki_nadrzedne_tak(
    jednostka_podrzedna, jednostka, client, uczelnia
):
    uczelnia.pokazuj_tylko_jednostki_nadrzedne = True
    uczelnia.save()

    url = reverse("bpp:browse_jednostki")
    res = client.get(url)
    assert JEDNOSTKA_UCZELNI in normalize_html(res.rendered_content)
    assert JEDNOSTKA_PODRZEDNA not in normalize_html(res.rendered_content)


@pytest.mark.parametrize("arg_res", [True, False])
def test_jednostka_pokazuj_opis(jednostka, client, arg_res):
    TESTSTR = "opis=foobar"
    jednostka.pokazuj_opis = arg_res
    jednostka.opis = TESTSTR
    jednostka.save()

    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    res = client.get(url)
    result = TESTSTR in normalize_html(res.rendered_content)
    assert result is arg_res
