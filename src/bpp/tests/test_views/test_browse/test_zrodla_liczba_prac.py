"""Lista źródeł: licznik prac z adnotacji (bez N+1) i poprawna odmiana
liczebników („2 publikacje”, „5 publikacji”, „12 publikacji”)."""

import pytest
from django.core.cache import cache
from django.db import connection
from django.template import Context, Template
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Zrodlo


def _dodaj_zrodla(od, do):
    for n in range(od, do):
        zrodlo = baker.make(Zrodlo, nazwa=f"Źródło testowe {n:02d}")
        baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo, _quantity=2)


def _liczba_zapytan(client):
    # Cache publiczny i zapamiętane literki zaniżyłyby drugi pomiar.
    cache.clear()
    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("bpp:browse_zrodla"))
    assert res.status_code == 200
    return len(ctx.captured_queries), res


@pytest.mark.django_db
def test_lista_zrodel_liczba_zapytan_nie_rosnie_z_liczba_kart(client, uczelnia):
    _dodaj_zrodla(0, 2)
    # Rozgrzewka: pierwsze żądanie w procesie płaci jednorazowe zapytania
    # (np. leniwie ładowana konfiguracja), niezależne od liczby kart.
    _liczba_zapytan(client)
    przed, res = _liczba_zapytan(client)
    assert len(res.context["object_list"]) == 2

    _dodaj_zrodla(2, 8)
    po, res = _liczba_zapytan(client)
    assert len(res.context["object_list"]) == 8

    assert po == przed


@pytest.mark.django_db
def test_lista_zrodel_licznik_prac_z_odmiana(client, uczelnia):
    uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych = True
    uczelnia.save()

    dwie = baker.make(Zrodlo, nazwa="Źródło z dwiema")
    baker.make(Wydawnictwo_Ciagle, zrodlo=dwie, _quantity=2)
    baker.make(Zrodlo, nazwa="Źródło bez prac")

    res = client.get(reverse("bpp:browse_zrodla"))
    tresc = res.rendered_content

    liczniki = {z.nazwa: z.liczba_prac for z in res.context["object_list"]}
    assert liczniki == {"Źródło z dwiema": 2, "Źródło bez prac": 0}

    assert "2 publikacje" in tresc
    # Źródło bez prac: pokazane, ale bez linii z licznikiem.
    assert "Źródło bez prac" in tresc
    assert "0 publikacji" not in tresc


@pytest.mark.parametrize(
    "wyraz,liczba,oczekiwane",
    [
        ("publikacja", 0, "publikacji"),
        ("publikacja", 1, "publikacja"),
        ("publikacja", 4, "publikacje"),
        ("publikacja", 12, "publikacji"),
        ("publikacja", 22, "publikacje"),
        ("źródło", 14, "źródeł"),
        ("źródło", 23, "źródła"),
        ("wydawca", 1, "wydawca"),
        ("wydawca", 3, "wydawców"),
    ],
)
def test_odmiana_liczebnikowa_w_szablonach_browse(wyraz, liczba, oczekiwane):
    tpl = Template(
        "{% load polish_inflection %}{% odmiana_liczebnikowa wyraz liczba %}"
    )
    assert tpl.render(Context({"wyraz": wyraz, "liczba": liczba})) == oczekiwane


def test_odmiana_liczebnikowa_biernik_na_stronie_roku():
    tpl = Template(
        '{% load polish_inflection %}{% odmiana_liczebnikowa "publikacja" n "biernik" %}'
    )
    assert tpl.render(Context({"n": 1})) == "publikację"
    assert tpl.render(Context({"n": 12})) == "publikacji"
