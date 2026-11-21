"""Filtry komparatora źródeł PBN wg okresu ewaluacji z paska okresu."""

from io import BytesIO
from unittest import mock

import pytest
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from pbn_komparator_zrodel.models import RozbieznoscZrodlaPBN

URL = "/komparator-zrodel-pbn/{slug}/"
URL_DYSCYPLINY = "/komparator-zrodel-pbn/{slug}/dyscypliny/"


@pytest.fixture
def zrodla():
    """Źródło „stare” (publikacja 2023) i „nowe” (publikacja 2027); każde
    z rozbieżnościami za 2024 i 2027."""
    stare = baker.make(Zrodlo, nazwa="Źródło stare")
    nowe = baker.make(Zrodlo, nazwa="Źródło nowe")
    baker.make(Wydawnictwo_Ciagle, zrodlo=stare, rok=2023)
    baker.make(Wydawnictwo_Ciagle, zrodlo=nowe, rok=2027)
    for zrodlo in (stare, nowe):
        for rok in (2024, 2027):
            RozbieznoscZrodlaPBN.objects.create(
                zrodlo=zrodlo,
                rok=rok,
                ma_rozbieznosc_punktow=True,
                ma_rozbieznosc_dyscyplin=True,
            )
    return stare, nowe


def _wiersze(response):
    return sorted((r.zrodlo.nazwa, r.rok) for r in response.context["rozbieznosci"])


@pytest.mark.django_db
@pytest.mark.parametrize("url", [URL, URL_DYSCYPLINY])
@pytest.mark.parametrize(
    "slug,oczekiwane",
    [
        ("2022-2025", [("Źródło stare", 2024)]),
        ("2026-2030", [("Źródło nowe", 2027)]),
    ],
)
def test_domyslnie_lata_i_publikacje_z_wybranego_okresu(
    admin_client, zrodla, url, slug, oczekiwane
):
    """Pierwsze wejście: zakres lat = wybrany okres, a filtr „tylko źródła
    z publikacjami w okresie” zaznaczony i liczony dla tego okresu."""
    response = admin_client.get(url.format(slug=slug))

    assert response.status_code == 200
    assert _wiersze(response) == oczekiwane
    rok_od, rok_do = (int(x) for x in slug.split("-"))
    assert response.context["rok_od"] == rok_od
    assert response.context["rok_do"] == rok_do
    assert response.context["tylko_z_publikacjami_w_okresie"] is True
    tresc = response.content.decode()
    assert 'name="tylko_z_publikacjami_w_okresie"' in tresc
    assert f"z publikacjami w latach {rok_od}–{rok_do}" in tresc


@pytest.mark.django_db
@pytest.mark.parametrize("url", [URL, URL_DYSCYPLINY])
def test_filtr_publikacji_wg_okresu_niezaleznie_od_zakresu_lat(
    admin_client, zrodla, url
):
    response = admin_client.get(
        url.format(slug="2026-2030"),
        {
            "rok_od": 2020,
            "rok_do": 2030,
            "tylko_rozbieznosci": "on",
            "tylko_z_publikacjami_w_okresie": "on",
        },
    )
    assert _wiersze(response) == [("Źródło nowe", 2024), ("Źródło nowe", 2027)]
    assert (
        "tylko_z_publikacjami_w_okresie=on" in response.context["filter_query_string"]
    )


@pytest.mark.django_db
def test_dawny_parametr_nadal_dziala(admin_client, zrodla):
    """Stare zakładki z ``bez_publikacji_2022_2025=on`` nie gubią filtra
    (liczonego teraz dla wybranego okresu)."""
    response = admin_client.get(
        URL.format(slug="2022-2025"),
        {
            "rok_od": 2020,
            "rok_do": 2030,
            "tylko_rozbieznosci": "on",
            "bez_publikacji_2022_2025": "on",
        },
    )
    assert _wiersze(response) == [("Źródło stare", 2024), ("Źródło stare", 2027)]


@pytest.mark.django_db
def test_odznaczony_filtr_pokazuje_wszystkie(admin_client, zrodla):
    response = admin_client.get(
        URL.format(slug="2026-2030"),
        {"rok_od": 2020, "rok_do": 2030, "tylko_rozbieznosci": "on"},
    )
    assert len(_wiersze(response)) == 4


@pytest.mark.django_db
@pytest.mark.parametrize(
    "slug,oczekiwane",
    [
        ("2022-2025", [("Źródło stare", 2024)]),
        ("2026-2030", [("Źródło nowe", 2027)]),
    ],
)
def test_eksport_dyscyplin_wg_okresu(admin_client, zrodla, slug, oczekiwane):
    response = admin_client.get(
        URL_DYSCYPLINY.format(slug=slug) + "eksport-xlsx/",
    )
    assert response.status_code == 200
    ws = load_workbook(BytesIO(response.content)).active
    wiersze = sorted((r[0], r[3]) for r in ws.iter_rows(min_row=2, values_only=True))
    assert wiersze == oczekiwane


@pytest.mark.django_db
def test_aktualizuj_wszystkie_dyscypliny_wg_okresu(admin_client, zrodla):
    """Masowa aktualizacja bierze rekordy wg okresu wybranego w adresie
    (pk liczone w widoku — zadanie Celery nie zna sesji)."""
    stare, nowe = zrodla
    with mock.patch(
        "pbn_komparator_zrodel.update_utils.aktualizuj_wiele_zrodel",
        return_value={"updated": 1, "errors": 0},
    ) as aktualizuj:
        response = admin_client.post(
            URL_DYSCYPLINY.format(slug="2026-2030") + "aktualizuj-wszystkie/"
        )
    assert response.status_code == 302
    (pks,), _kwargs = aktualizuj.call_args
    assert list(pks) == [
        RozbieznoscZrodlaPBN.objects.get(zrodlo=nowe, rok=2027).pk,
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "slug,oczekiwane",
    [
        ("2022-2025", [("Źródło stare", 2024)]),
        ("2026-2030", [("Źródło nowe", 2027)]),
    ],
)
def test_eksport_punktow_jak_lista(admin_client, zrodla, slug, oczekiwane):
    """Eksport XLSX punktów stosuje te same filtry co lista, łącznie
    z „tylko źródła z publikacjami w okresie” — obejmuje to, co widać."""
    lista = admin_client.get(URL.format(slug=slug))
    assert _wiersze(lista) == oczekiwane

    response = admin_client.get(URL.format(slug=slug) + "eksport-xlsx/")
    assert response.status_code == 200
    ws = load_workbook(BytesIO(response.content)).active
    wiersze = sorted((r[0], r[3]) for r in ws.iter_rows(min_row=2, values_only=True))
    assert wiersze == oczekiwane
