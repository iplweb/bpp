"""Lata z wyszukiwarki autora: zakresy jako pole „Zakres lat”.

Selektor lat (zakres-lat.js) wysyła ciągłe zakresy jako ``zakres_lat=[od,do]``,
a pojedyncze lata jako ``rok``. BuildSearch łączy je OR w jednej grupie.
"""

import json

import pytest
from django.urls import reverse
from model_bakery import baker
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.models import Autor, BppMultiseekVisibility, Wydawnictwo_Ciagle
from bpp.multiseek_registry import registry


def _grupa_lat(client):
    dane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    grupy = [f for f in dane["form_data"] if isinstance(f, list)]
    assert len(grupy) == 1, dane["form_data"]
    return dane, [f for f in grupy[0] if isinstance(f, dict)]


@pytest.mark.django_db
def test_zakres_i_pojedynczy_rok_w_jednej_grupie_or(
    admin_client, standard_data, jednostka, denorms
):
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    prace = {}
    for rok in (2017, 2018, 2020, 2022, 2024, 2025):
        p = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"Praca {rok}", rok=rok)
        p.dodaj_autora(autor, jednostka)
        prace[rok] = p
    denorms.flush()

    resp = admin_client.post(
        reverse("bpp:browse_build_search"),
        {"autor": str(autor.pk), "zakres_lat": "[2020,2024]", "rok": "2017"},
    )
    assert resp.status_code == 302

    dane, pola = _grupa_lat(admin_client)
    assert [(f["field"], f["value"], f["prev_op"]) for f in pola] == [
        ("Rok", "2017", None),
        ("Zakres lat", "[2020,2024]", "or"),
    ]

    lata = set(registry.get_query_for_model(dane).values_list("rok", flat=True))
    assert lata == {2017, 2020, 2022, 2024}


@pytest.mark.django_db
def test_lata_niesasiadujace_zostaja_polami_rok(client):
    autor = baker.make(Autor)
    client.post(
        reverse("bpp:browse_build_search"),
        {"autor": str(autor.pk), "rok": ["2020", "2022"]},
    )
    _, pola = _grupa_lat(client)
    assert [(f["field"], f["value"]) for f in pola] == [
        ("Rok", "2020"),
        ("Rok", "2022"),
    ]


@pytest.mark.django_db
def test_ukryte_pole_zakres_lat_rozwija_sie_na_lata(client):
    autor = baker.make(Autor)
    # Pierwsze odpytanie tworzy wiersz widoczności — potem go chowamy.
    registry.get_fields(None)
    BppMultiseekVisibility.objects.filter(field_name="zakres_lat").update(public=False)

    client.post(
        reverse("bpp:browse_build_search"),
        {"autor": str(autor.pk), "zakres_lat": "[2022,2020]"},
    )
    _, pola = _grupa_lat(client)
    assert [(f["field"], f["value"]) for f in pola] == [
        ("Rok", "2020"),
        ("Rok", "2021"),
        ("Rok", "2022"),
    ]


@pytest.mark.django_db
def test_smieciowy_zakres_przy_ukrytym_polu_jest_pomijany(client):
    autor = baker.make(Autor)
    registry.get_fields(None)
    BppMultiseekVisibility.objects.filter(field_name="zakres_lat").update(public=False)
    resp = client.post(
        reverse("bpp:browse_build_search"),
        {"autor": str(autor.pk), "zakres_lat": "nie-json", "rok": "2020"},
    )
    assert resp.status_code == 302
    pola = [
        f
        for f in json.loads(client.session[MULTISEEK_SESSION_KEY])["form_data"]
        if isinstance(f, dict) and f["field"] in ("Rok", "Zakres lat")
    ]
    assert [(f["field"], f["value"]) for f in pola] == [("Rok", "2020")]


def _pola_lat(client):
    dane = json.loads(client.session[MULTISEEK_SESSION_KEY])
    pola = []
    for f in dane["form_data"]:
        for g in f if isinstance(f, list) else [f]:
            if isinstance(g, dict) and g["field"] in ("Rok", "Zakres lat"):
                pola.append((g["field"], g["value"]))
    return pola


@pytest.mark.django_db
@pytest.mark.parametrize(
    "post,oczekiwane",
    [
        # Przypadek z rozmowy: 2020 + 2022–2025, dokliknięty 2021.
        (
            {"rok": ["2020", "2021"], "zakres_lat": "[2022,2025]"},
            [("Zakres lat", "[2020,2025]")],
        ),
        # Kolejne lata bez zakresu (np. bez JS) też się kompresują.
        ({"rok": ["2019", "2020", "2021"]}, [("Zakres lat", "[2019,2021]")]),
        # Nakładające się zakresy scalone, samotny rok zostaje.
        (
            {"rok": "2010", "zakres_lat": ["[2018,2021]", "[2020,2023]"]},
            [("Rok", "2010"), ("Zakres lat", "[2018,2023]")],
        ),
        # Śmieci pomijane, w tym absurdalnie szeroki zakres.
        ({"rok": ["x", "2020"], "zakres_lat": "[0,999999]"}, [("Rok", "2020")]),
    ],
)
def test_kompresja_lat(client, post, oczekiwane):
    autor = baker.make(Autor)
    client.post(reverse("bpp:browse_build_search"), {"autor": str(autor.pk), **post})
    assert _pola_lat(client) == oczekiwane
