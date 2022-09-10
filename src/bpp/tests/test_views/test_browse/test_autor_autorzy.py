from datetime import date

import pytest

from bpp.tests import normalize_html

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from model_bakery import baker

from fixtures import NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD

from bpp.models import (
    Autor_Jednostka,
    Funkcja_Autora,
    Jednostka,
    OpcjaWyswietlaniaField,
    Praca_Doktorska,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
)
from bpp.models.autor import Autor


def test_autor_ukrywanie_nazwisk(autor_jan_nowak, client, admin_client):
    NAZWISKO = "NazwiskoAutora"
    autor_jan_nowak.poprzednie_nazwiska = NAZWISKO
    assert NAZWISKO in str(autor_jan_nowak)

    autor_jan_nowak.pokazuj_poprzednie_nazwiska = False
    autor_jan_nowak.save()

    assert NAZWISKO not in str(autor_jan_nowak)

    url = reverse("bpp:browse_autor", args=(autor_jan_nowak.slug,))

    page = admin_client.get(url)
    assert NAZWISKO in normalize_html(page.rendered_content)

    page = client.get(url)
    assert NAZWISKO not in normalize_html(page.rendered_content)


@pytest.mark.django_db
def test_AutorView_funkcja_za_nazwiskiem(app):
    autor = baker.make(Autor, nazwisko="Foo", imiona="Bar")
    jednostka = baker.make(Jednostka, nazwa="Jednostka")
    funkcja = Funkcja_Autora.objects.create(
        nazwa="profesor uczelni", skrot="prof. ucz."
    )
    aj = Autor_Jednostka.objects.create(
        autor=autor, jednostka=jednostka, funkcja=funkcja
    )

    url = reverse("bpp:browse_autor", args=(autor.slug,))

    page = app.get(url)
    assert page.status_code == 200
    res = normalize_html(str(page.content, "utf-8"))
    assert res.find("<h1>Foo Bar </h1>") >= 0

    aj.rozpoczal_prace = date(2020, 1, 1)
    aj.save()

    page = app.get(url)
    res = normalize_html(str(page.content, "utf-8"))
    assert res.find("<h1>Foo Bar </h1>") >= 0

    funkcja.pokazuj_za_nazwiskiem = True
    funkcja.save()

    page = app.get(url)
    res = normalize_html(str(page.content, "utf-8"))
    assert res.find("<h1>Foo Bar, profesor uczelni </h1>") >= 0


@pytest.fixture
def test_browse_autor():
    Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")

    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    wc = baker.make(Wydawnictwo_Ciagle, liczba_cytowan=200)
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Jan K")

    j2 = baker.make(Jednostka, skupia_pracownikow=False)
    wc2 = baker.make(Wydawnictwo_Ciagle, liczba_cytowan=300)
    wc2.dodaj_autora(autor, j2, zapisany_jako="Jan K2", afiliuje=False)

    return autor


def test_browse_autor_dwa_doktoraty(typy_odpowiedzialnosci, autor_jan_kowalski, client):
    tytuly_prac = ["Praca 1", "Praca 2"]
    for praca in tytuly_prac:
        baker.make(Praca_Doktorska, tytul_oryginalny=praca, autor=autor_jan_kowalski)

    res = client.get(
        reverse(
            "bpp:browse_autor",
            kwargs=dict(
                slug=autor_jan_kowalski.slug,
            ),
        )
    )

    for praca in tytuly_prac:
        assert praca in res.content.decode("utf-8")


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

    content = normalize_html(res.rendered_content)
    assert "Liczba cytowań" in content
    assert "Liczba cytowań: </strong>500" in content
    assert "Liczba cytowań z jednostek afiliowanych: </strong>200" in content


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
