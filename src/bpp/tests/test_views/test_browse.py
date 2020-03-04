# -*- encoding: utf-8 -*-
import json
import re

import pytest
from bs4 import BeautifulSoup
from django.contrib.contenttypes.models import ContentType

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from model_mommy import mommy
from multiseek.logic import EQUAL_NONE, EQUAL, EQUAL_FEMALE
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.models import (
    Jednostka,
    Wydawnictwo_Ciagle,
    OpcjaWyswietlaniaField,
    Typ_Odpowiedzialnosci,
)
from bpp.models.autor import Autor
from bpp.views.browse import BuildSearch
from conftest import NORMAL_DJANGO_USER_PASSWORD, NORMAL_DJANGO_USER_LOGIN
from miniblog.models import Article


def test_buildSearch(settings):
    dct = {
        "zrodlo": [1,],
        "typ": [1,],
        "rok": [2013,],
        "jednostka": [1,],
        "autor": [1,],
    }

    class mydct(dict):
        def getlist(self, value):
            return self.get(value)

    class request:
        POST = mydct(dct)
        META = {}
        session = {}

        def build_absolute_uri(self, *args, **kw):
            return "/absolute/uri"

    settings.LANGUAGE_CODE = "en"
    tbs = BuildSearch()
    tbs.request = request()
    tbs.post(request)

    expected = {
        "form_data": [
            None,
            {
                "field": "\u0179r\xf3d\u0142o",
                "operator": str(EQUAL_NONE),
                "prev_op": None,
                "value": 1,
            },
            {
                "field": "Nazwisko i imi\u0119",
                "operator": str(EQUAL_NONE),
                "prev_op": "and",
                "value": 1,
            },
            {
                "field": "Typ rekordu",
                "operator": str(EQUAL),
                "prev_op": "and",
                "value": 1,
            },
            {
                "field": "Jednostka",
                "operator": str(EQUAL_FEMALE),
                "prev_op": "and",
                "value": 1,
            },
            {"field": "Rok", "operator": str(EQUAL), "prev_op": "and", "value": 2013},
        ]
    }

    assert json.loads(request.session[MULTISEEK_SESSION_KEY]) == expected


pattern = re.compile("Strona WWW")


def nastepna_komorka_po_strona_www(dokument):
    soup = BeautifulSoup(dokument, "html.parser")
    return soup.find("th", text=pattern).parent.find("td").text.strip()


@pytest.mark.django_db
def test_darmowy_platny_dostep_www_wyswietlanie(client, wydawnictwo_ciagle):
    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()
    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        )
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "Brak danych"

    wydawnictwo_ciagle.www = "platny"
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()
    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        )
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "platny"

    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        )
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "darmowy"

    wydawnictwo_ciagle.www = "jezeli sa oba ma byc darmowy"
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        )
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "darmowy"


@pytest.mark.django_db
def test_artykuly(uczelnia, client):
    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert res.status_code == 200

    TYTUL = "Tytul testowego artykulu"

    a = Article.objects.create(
        title=TYTUL, article_body="456", status=Article.STATUS.draft, slug="1"
    )

    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert TYTUL.encode("utf-8") not in res.content

    a.status = Article.STATUS.published
    a.save()

    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert TYTUL.encode("utf-8") in res.content


@pytest.mark.django_db
def test_artykul_ze_skrotem(uczelnia, client):
    a = Article.objects.create(
        title="123",
        article_body="456\n<!-- tutaj -->\n789",
        status=Article.STATUS.published,
        slug="1",
    )

    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert b"789" not in res.content
    assert "więcej" in res.rendered_content

    res = client.get(reverse("bpp:browse_artykul", args=(uczelnia.slug, a.slug)))
    assert b"789" in res.content


@pytest.mark.django_db
def test_jednostka_nie_wyswietlaj_autorow_gdy_wielu(client, jednostka):
    for n in range(102):
        jednostka.dodaj_autora(mommy.make(Autor))

    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))
    assert "... napisane przez" not in res.rendered_content


@pytest.fixture
def test_browse_autor():
    Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")

    autor = mommy.make(Autor)
    jednostka = mommy.make(Jednostka, skupia_pracownikow=True)
    wc = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=200)
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Jan K")

    j2 = mommy.make(Jednostka, skupia_pracownikow=False)
    wc2 = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=300)
    wc2.dodaj_autora(autor, j2, zapisany_jako="Jan K2", afiliuje=False)

    return autor


@pytest.mark.django_db
def test_browse_autor_podstrona_liczba_cytowan_nigdy(
    client, uczelnia, test_browse_autor
):
    uczelnia.pokazuj_liczbe_cytowan_na_stronie_autora = (
        OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    )
    uczelnia.save()

    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))
    assert "Liczba cytowań" not in res.rendered_content


@pytest.mark.django_db
def test_browse_autor_podstrona_liczba_cytowan_zawsze(
    client, uczelnia, test_browse_autor
):
    uczelnia.pokazuj_liczbe_cytowan_na_stronie_autora = (
        OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    )
    uczelnia.save()

    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))

    assert "Liczba cytowań" in res.rendered_content
    assert "Liczba cytowań: </strong>500" in res.rendered_content
    assert (
        "Liczba cytowań z jednostek afiliowanych: </strong>200" in res.rendered_content
    )


@pytest.mark.django_db
def test_browse_autor_podstrona_liczba_cytowan_zalogowani(
    client, uczelnia, test_browse_autor, normal_django_user
):
    uczelnia.pokazuj_liczbe_cytowan_na_stronie_autora = (
        OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    )
    uczelnia.save()

    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))
    assert "Liczba cytowań" not in res.rendered_content

    client.login(
        username=NORMAL_DJANGO_USER_LOGIN, password=NORMAL_DJANGO_USER_PASSWORD
    )
    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))
    assert "Liczba cytowań" in res.rendered_content


@pytest.mark.django_db
def test_browse_snip_visible(client, uczelnia, wydawnictwo_ciagle):
    wydawnictwo_ciagle.punktacja_snip = 50
    wydawnictwo_ciagle.save()

    uczelnia.pokazuj_punktacja_snip = True
    uczelnia.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        )
    )

    assert b"SNIP" in res.content


@pytest.mark.django_db
def test_browse_snip_invisible(client, uczelnia, wydawnictwo_ciagle):
    wydawnictwo_ciagle.punktacja_snip = 50
    wydawnictwo_ciagle.save()

    uczelnia.pokazuj_punktacja_snip = False
    uczelnia.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        )
    )

    assert b"SNIP" not in res.content
