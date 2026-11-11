"""Przeglądanie wydawców: indeks A–Z, strona wydawcy, pole „Wydawca”
w multiseeku (razem z aliasami) i kafel na stronie głównej."""

import json

import pytest
from django.urls import reverse
from model_bakery import baker
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.models import Wydawca, Wydawnictwo_Zwarte
from bpp.multiseek_registry import registry


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
    resp = client.get(reverse("bpp:browse_wydawca", args=(glowny.pk,)))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert "2 publikacje w bazie" in html
    assert "data-zakres-lat" in html
    assert "Publikacje w latach" in html
    assert f'name="wydawca" value="{glowny.pk}"' in html
    assert alias.nazwa in html  # sekcja „Także jako”


def test_alias_przekierowuje_na_wydawce(client, wydawcy):
    glowny, alias, _pusty = wydawcy
    resp = client.get(reverse("bpp:browse_wydawca", args=(alias.pk,)))
    assert resp.status_code == 301
    assert resp["Location"] == reverse("bpp:browse_wydawca", args=(glowny.pk,))


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


@pytest.fixture
def wydawca_ksiazki_rozdzialy(db, standard_data):
    """Wydawca z dwiema książkami (2020, 2021) i trzema rozdziałami (2021)."""
    from bpp import const
    from bpp.models import Charakter_Formalny

    ksiazka = baker.make(
        Charakter_Formalny,
        nazwa="Książka testowa",
        skrot="KST",
        charakter_ogolny=const.CHARAKTER_OGOLNY_KSIAZKA,
    )
    rozdzial = baker.make(
        Charakter_Formalny,
        nazwa="Rozdział testowy",
        skrot="RZT",
        charakter_ogolny=const.CHARAKTER_OGOLNY_ROZDZIAL,
    )
    wydawca = baker.make(Wydawca, nazwa="Wydawnictwo Książkowe")
    for rok in (2020, 2021):
        baker.make(
            Wydawnictwo_Zwarte,
            tytul_oryginalny=f"Monografia {rok}",
            rok=rok,
            wydawca=wydawca,
            charakter_formalny=ksiazka,
        )
    for nr in range(3):
        baker.make(
            Wydawnictwo_Zwarte,
            tytul_oryginalny=f"Rozdział {nr}",
            rok=2021,
            wydawca=wydawca,
            charakter_formalny=rozdzial,
        )
    return wydawca


def test_podzial_wydawcy_na_ksiazki_i_rozdzialy(wydawca_ksiazki_rozdzialy):
    from bpp.podzial_wydawcy import podzial_wydawcy

    wynik = podzial_wydawcy(wydawca_ksiazki_rozdzialy.prace())
    assert [(k["wartosc"], k["opis"]) for k in wynik["podzial"]] == [
        ("książka", "2 książki"),
        ("rozdział", "3 rozdziały"),
    ]
    wykresy = {w["nazwa"]: w for w in wynik["wykresy_kategorii"]}
    assert wykresy["Książki w latach"]["dane"]["dane"] == [(2020, 1), (2021, 1)]
    assert wykresy["Rozdziały w latach"]["dane"]["dane"] == [(2021, 3)]
    assert wykresy["Rozdziały w latach"]["pola"] == [("charakter_ogolny", "rozdział")]


@pytest.mark.parametrize(
    "liczba,opis",
    [(1, "1 książka"), (4, "4 książki"), (5, "5 książek"), (12, "12 książek")],
)
def test_odmiana_liczby_ksiazek(liczba, opis):
    from bpp.podzial_wydawcy import KATEGORIE, _forma

    assert f"{liczba} {_forma(liczba, KATEGORIE[0][2])}" == opis


def test_strona_wydawcy_ksiazki_i_rozdzialy(client, wydawca_ksiazki_rozdzialy):
    html = client.get(wydawca_ksiazki_rozdzialy.get_absolute_url()).content.decode()
    assert "2 książki" in html
    assert "3 rozdziały" in html
    assert "Książki w latach" in html
    assert "Rozdziały w latach" in html
    assert "Publikacje w latach" not in html
    assert 'name="charakter_ogolny" value="książka"' in html
    assert 'name="charakter_ogolny" value="rozdział"' in html


def test_build_search_tylko_rozdzialy_wydawcy(client, wydawca_ksiazki_rozdzialy):
    resp = client.post(
        reverse("bpp:browse_build_search"),
        {
            "wydawca": str(wydawca_ksiazki_rozdzialy.pk),
            "charakter_ogolny": "rozdział",
        },
    )
    assert resp.status_code == 302
    dane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    tytuly = set(
        registry.get_query_for_model(dane).values_list("tytul_oryginalny", flat=True)
    )
    assert tytuly == {"Rozdział 0", "Rozdział 1", "Rozdział 2"}
