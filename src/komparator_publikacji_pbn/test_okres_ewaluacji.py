"""Komparator publikacji PBN wg okresu ewaluacji (FD#514)."""

from io import BytesIO

import pytest
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Wydawnictwo_Ciagle
from ewaluacja_common.okres import okres_domyslny
from pbn_api.models import Publication

URL = "/komparator-publikacji-pbn/"
URL_OKRESU = "/komparator-publikacji-pbn/{slug}/"


@pytest.fixture
def prace(db):
    """Prace z różnicą w tytule z lat 2020, 2023 i 2027."""
    for rok in (2020, 2023, 2027):
        pbn = baker.make(
            Publication,
            mongoId=f"rok{rok}",
            title=f"Tytuł w PBN {rok}",
            year=rok,
            status="ACTIVE",
            versions=[{"current": True, "object": {"title": f"Tytuł w PBN {rok}"}}],
        )
        baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny=f"Tytuł w BPP {rok}",
            rok=rok,
            pbn_uid=pbn,
        )


def _lata(response):
    return sorted(c["bpp_publication"].rok for c in response.context["comparisons"])


@pytest.mark.parametrize(
    "slug,oczekiwane", [("2022-2025", [2023]), ("2026-2030", [2027])]
)
def test_domyslny_zakres_lat_to_wybrany_okres(admin_client, prace, slug, oczekiwane):
    """Bez ręcznego zakresu komparator porównuje prace z lat okresu z paska
    (dawniej zawsze 2022–2025) i pokazuje ten zakres w nagłówku."""
    response = admin_client.get(URL_OKRESU.format(slug=slug))

    assert response.status_code == 200
    assert _lata(response) == oczekiwane
    rok_od, rok_do = slug.split("-")
    assert response.context["year_min"] == rok_od
    assert response.context["year_max"] == rok_do
    tresc = response.content.decode()
    assert f"publikacje z lat {rok_od}–{rok_do}" in tresc
    assert "pasek-okresu" in tresc


def test_bez_okresu_w_adresie_okres_domyslny(admin_client, prace):
    okres = okres_domyslny()

    response = admin_client.get(URL)

    assert response.context["year_min"] == str(okres.rok_od)
    assert response.context["year_max"] == str(okres.rok_do)


def test_reczny_zakres_zapamietany_w_obrebie_okresu(admin_client, prace):
    """Strażnik: ręczny zakres lat działa i jest pamiętany (sesja) przy
    kolejnych wejściach w tym samym okresie, np. przy zmianie strony."""
    url = URL_OKRESU.format(slug="2026-2030")

    response = admin_client.get(url, {"year_min": 2020, "year_max": 2023})
    assert _lata(response) == [2020, 2023]

    response = admin_client.get(url, {"page": 1})
    assert _lata(response) == [2020, 2023]
    assert response.context["year_min"] == "2020"


def test_zmiana_okresu_przywraca_lata_okresu_reszta_filtrow_zostaje(
    admin_client, prace
):
    """Zakres lat zapamiętany w jednym okresie nie przenosi się do drugiego
    (inaczej pasek pokazywałby 2026–2030, a lista lata 2022–2025); pozostałe
    filtry zostają."""
    admin_client.get(
        URL_OKRESU.format(slug="2022-2025"),
        {"year_min": 2020, "year_max": 2023, "type": "ciagle", "fields": "title"},
    )

    response = admin_client.get(URL_OKRESU.format(slug="2026-2030"))

    assert _lata(response) == [2027]
    assert response.context["year_min"] == "2026"
    assert response.context["year_max"] == "2030"
    assert response.context["publication_type"] == "ciagle"
    assert response.context["enabled_fields"] == ["title"]


def test_filtry_sprzed_zmiany_bez_okresu_w_sesji(admin_client, prace):
    """Sesja zapisana przed tą zmianą (lata 2022–2025, bez okresu) nie blokuje
    użytkownika na starym okresie."""
    sesja = admin_client.session
    sesja["komparator_publikacji_filters"] = {
        "query": "",
        "publication_type": "all",
        "year_min": "2022",
        "year_max": "2025",
        "enabled_fields": ["title"],
    }
    sesja.save()

    response = admin_client.get(URL_OKRESU.format(slug="2026-2030"))

    assert _lata(response) == [2027]


def test_eksport_xlsx_respektuje_okres_i_adres_jest_zakodowany(admin_client, prace):
    """Link eksportu niesie lata okresu, a fraza z „&” nie rozbija adresu."""
    url = URL_OKRESU.format(slug="2026-2030")

    response = admin_client.get(url, {"q": "Tytuł & reszta"})
    export_url = response.context["export_url"]
    assert "year_min=2026" in export_url and "year_max=2030" in export_url
    assert "q=Tytu%C5%82+%26+reszta" in export_url

    response = admin_client.get(url + "?export=xlsx&year_min=2026&year_max=2030")
    assert response.status_code == 200
    arkusz = load_workbook(BytesIO(response.content)).active
    lata = {wiersz[4] for wiersz in arkusz.iter_rows(min_row=2, values_only=True)}
    assert lata == {2027}


def test_porownania_liczone_raz_na_zadanie(admin_client, prace, mocker):
    """Lista porównań nie jest liczona dwa razy przy jednym wyświetleniu."""
    from komparator_publikacji_pbn.views import PublicationComparisonView

    szpieg = mocker.spy(PublicationComparisonView, "get_queryset")

    admin_client.get(URL_OKRESU.format(slug="2026-2030"))

    assert szpieg.call_count == 1
