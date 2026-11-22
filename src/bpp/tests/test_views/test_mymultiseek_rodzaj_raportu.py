"""Zmiana rodzaju raportu („Widok”) prosto ze strony wyników wyszukiwania."""

import json

import pytest
from django.urls import reverse
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.multiseek_registry import registry

pytestmark = pytest.mark.django_db


def _indeks(client, raport):
    """Indeks rodzaju raportu tak, jak go widzi anonim (publiczne rodzaje)."""
    publiczne = [typ.id for typ in registry.report_types if typ.public]
    return str(publiczne.index(raport))


def test_strona_wynikow_ma_menu_widok(client, uczelnia):
    tresc = client.get(reverse("multiseek:results")).content.decode()
    assert "Widok: lista" in tresc
    assert 'name="raport" value="table"' in tresc
    # rodzaje niepubliczne nie są proponowane niezalogowanemu
    assert 'name="raport" value="numer_list"' not in tresc


def test_zmiana_rodzaju_raportu_zachowuje_zapytanie(client, uczelnia):
    zapytanie = {"form_data": [None], "ordering": {"ordering_0": "1"}}
    sesja = client.session
    sesja[MULTISEEK_SESSION_KEY] = json.dumps(zapytanie)
    sesja.save()

    res = client.post(reverse("multiseek-rodzaj-raportu"), {"raport": "table"})
    assert res.status_code == 302
    assert res["Location"].endswith(reverse("multiseek:results"))

    zapisane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    assert zapisane["report_type"] == _indeks(client, "table")
    assert zapisane["form_data"] == zapytanie["form_data"]
    assert zapisane["ordering"] == zapytanie["ordering"]
    assert "Widok: tabela" in client.get(res["Location"]).content.decode()


def test_zmiana_rodzaju_raportu_bez_zapytania_w_sesji(client, uczelnia):
    res = client.post(reverse("multiseek-rodzaj-raportu"), {"raport": "table"})
    assert res.status_code == 302
    assert "Widok: tabela" in client.get(res["Location"]).content.decode()


def test_niedostepny_rodzaj_raportu_nic_nie_zmienia(client, uczelnia):
    """Rodzaj niepubliczny (albo nieistniejący) — anonim zostaje przy swoim."""
    for raport in ("numer_list", "nie-ma-takiego", ""):
        res = client.post(reverse("multiseek-rodzaj-raportu"), {"raport": raport})
        assert res.status_code == 302
        assert MULTISEEK_SESSION_KEY not in client.session


def test_zmiana_rodzaju_raportu_tylko_post(client, uczelnia):
    assert client.get(reverse("multiseek-rodzaj-raportu")).status_code == 405
