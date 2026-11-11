"""Przeglądanie wydawców: indeks A–Z, strona wydawcy, pole „Wydawca”
w multiseeku (razem z aliasami) i kafel na stronie głównej."""

import importlib
import json

import pytest
from django.apps import apps
from django.urls import reverse
from model_bakery import baker
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.models import Wydawca, Wydawnictwo_Zwarte
from bpp.multiseek_registry import registry
from bpp.util.text import slugify_wydawca


@pytest.fixture
def wydawcy(db, standard_data):
    """Główny wydawca z aliasem, drugi wydawca bez prac."""
    glowny = baker.make(Wydawca, nazwa="Akademickie Wydawnictwo")
    alias = baker.make(Wydawca, nazwa="Wyd. Akademickie", alias_dla=glowny)
    pusty = baker.make(Wydawca, nazwa="Bez Prac")
    baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Książka 2020", rok=2020, wydawca=glowny
    )
    baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Książka 2022", rok=2022, wydawca=alias
    )
    return glowny, alias, pusty


def test_wszystkie_pk_z_aliasami_posrednimi(db):
    a = baker.make(Wydawca, nazwa="A")
    b = baker.make(Wydawca, nazwa="B", alias_dla=a)
    c = baker.make(Wydawca, nazwa="C", alias_dla=b)
    baker.make(Wydawca, nazwa="D")
    assert a.wszystkie_pk() == sorted([a.pk, b.pk, c.pk])


def test_indeks_wydawcow_tylko_glowni_z_pracami(client, wydawcy):
    glowny, alias, pusty = wydawcy
    resp = client.get(reverse("bpp:browse_wydawcy"))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert glowny.nazwa in html
    assert "2 publikacje" in html  # praca aliasu liczona u głównego
    assert alias.nazwa not in html
    assert pusty.nazwa not in html


def test_indeks_wydawcow_literka_i_szukanie(client, wydawcy):
    glowny, _alias, _pusty = wydawcy
    html = client.get(reverse("bpp:browse_wydawcy_literka", args=("A",))).content
    assert glowny.nazwa in html.decode()
    html = client.get(reverse("bpp:browse_wydawcy_literka", args=("Z",))).content
    assert glowny.nazwa not in html.decode()
    html = client.get(reverse("bpp:browse_wydawcy") + "?search=akadem").content
    assert glowny.nazwa in html.decode()


def test_strona_wydawcy(client, wydawcy):
    glowny, alias, _pusty = wydawcy
    resp = client.get(reverse("bpp:browse_wydawca", args=(glowny.slug,)))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert "2 publikacje w bazie" in html
    assert "data-zakres-lat" in html
    assert "Publikacje w latach" in html
    assert f'name="wydawca" value="{glowny.pk}"' in html
    assert alias.nazwa in html  # sekcja „Także jako”


def test_get_absolute_url_po_slugu_toplevelu(wydawcy):
    glowny, alias, _pusty = wydawcy
    url = reverse("bpp:browse_wydawca", args=(glowny.slug,))
    assert glowny.get_absolute_url() == url
    assert alias.get_absolute_url() == url


def test_indeks_wydawcow_linkuje_po_slugu(client, wydawcy):
    glowny, _alias, _pusty = wydawcy
    html = client.get(reverse("bpp:browse_wydawcy")).content.decode()
    assert f'href="{glowny.get_absolute_url()}"' in html


def test_alias_przekierowuje_na_wydawce(client, wydawcy):
    glowny, alias, _pusty = wydawcy
    resp = client.get(reverse("bpp:browse_wydawca", args=(alias.slug,)))
    assert resp.status_code == 301
    assert resp["Location"] == reverse("bpp:browse_wydawca", args=(glowny.slug,))


def test_stary_adres_po_pk_przekierowuje_na_slug(client, wydawcy):
    glowny, alias, _pusty = wydawcy
    oczekiwany = reverse("bpp:browse_wydawca", args=(glowny.slug,))
    for wydawca in (glowny, alias):
        resp = client.get(f"/bpp/wydawca/{wydawca.pk}/")
        assert resp.status_code == 301
        assert resp["Location"] == oczekiwany


def test_nieistniejacy_wydawca_404(client, db):
    assert client.get("/bpp/wydawca/999999999/").status_code == 404
    assert client.get("/bpp/wydawca/nie-ma-takiego/").status_code == 404


@pytest.mark.parametrize(
    "nazwa,slug",
    [
        ("1984", "wydawca-1984"),
        ("Wydawnictwo Naukowe PWN", "Wydawnictwo-Naukowe-PWN"),
        ("Łódź 2000", "Lodz-2000"),
        ("", ""),
    ],
)
def test_slugify_wydawca(nazwa, slug):
    assert slugify_wydawca(nazwa) == slug
    assert slugify_wydawca(slugify_wydawca(nazwa)) == slug


@pytest.mark.django_db
def test_slug_wydawcy_z_samych_cyfr_i_unikalny(client):
    a = Wydawca.objects.create(nazwa="1984")
    b = Wydawca.objects.create(nazwa="1984.")  # ten sam slug bazowy
    assert a.slug == "wydawca-1984"
    assert b.slug == "wydawca-1984-2"
    assert client.get(a.get_absolute_url()).status_code == 200
    # Adres po pk nadal przekierowuje, nie jest brany za slug.
    resp = client.get(f"/bpp/wydawca/{a.pk}/")
    assert resp.status_code == 301
    assert resp["Location"] == a.get_absolute_url()


@pytest.mark.django_db
def test_migracja_wypelnia_unikalne_slugi():
    migracja = importlib.import_module("bpp.migrations.0504_wydawca_slug_dane")
    a = Wydawca.objects.create(nazwa="2001")
    b = Wydawca.objects.create(nazwa="2001!")
    c = Wydawca.objects.create(nazwa="Inne Wydawnictwo", alias_dla=a)
    for w in (a, b, c):  # „stare” wartości, które migracja nadpisze
        Wydawca.objects.filter(pk=w.pk).update(slug=f"stary-{w.pk}")

    migracja.wypelnij_slugi(apps, None)

    slugi = dict(Wydawca.objects.values_list("pk", "slug"))
    assert slugi[a.pk] == "wydawca-2001"
    assert slugi[b.pk] == "wydawca-2001-2"
    assert slugi[c.pk] == "Inne-Wydawnictwo"
    assert len(set(slugi.values())) == len(slugi)


def test_build_search_wydawca_lapie_prace_aliasow(client, wydawcy):
    glowny, _alias, _pusty = wydawcy
    resp = client.post(
        reverse("bpp:browse_build_search"),
        {"wydawca": str(glowny.pk), "rok": ["2020", "2021", "2022"]},
    )
    assert resp.status_code == 302
    dane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    pola = [f for f in dane["form_data"] if isinstance(f, dict)]
    assert ("Wydawca", str(glowny.pk)) in [(f["field"], f["value"]) for f in pola]

    tytuly = set(
        registry.get_query_for_model(dane).values_list("tytul_oryginalny", flat=True)
    )
    assert tytuly == {"Książka 2020", "Książka 2022"}


def test_publiczny_autocomplete_wydawcy_bez_logowania(client, wydawcy):
    glowny, alias, _pusty = wydawcy
    resp = client.get(reverse("bpp:public-wydawca-autocomplete") + "?q=Akademickie")
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["results"]}
    assert str(glowny.pk) in ids
    assert str(alias.pk) not in ids


@pytest.mark.django_db
def test_kafel_wydawcow_na_stronie_glownej(client, uczelnia):
    html = client.get("/").content.decode()
    assert reverse("bpp:browse_wydawcy") in html
    assert "Wydawcy" in html
