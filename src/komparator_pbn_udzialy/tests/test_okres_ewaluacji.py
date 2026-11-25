"""Lista „Problemy PBN” (komparator udziałów) wg okresu ewaluacji (FD#514)."""

import pytest
from model_bakery import baker

from ewaluacja_common.okres import okres_domyslny
from komparator_pbn_udzialy.models import BrakAutoraWPublikacji

URL = "/komparator-pbn-udzialy/"
URL_OKRESU = "/komparator-pbn-udzialy/{slug}/"


def _brak_autora(rok, nazwisko, tytul="Praca"):
    naukowiec = baker.make("pbn_api.Scientist", name="Jan", lastName=nazwisko)
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=naukowiec,
        publicationId=baker.make("pbn_api.Publication", year=rok, title=tytul),
    )
    return BrakAutoraWPublikacji.objects.create(
        pbn_scientist=naukowiec,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
    )


@pytest.fixture
def problemy(db):
    """Po jednym problemie z każdego okresu: 2023 („Stary”) i 2027 („Nowy”)."""
    return _brak_autora(2023, "Stary"), _brak_autora(2027, "Nowy")


def _nazwiska(response):
    return sorted(p.obj.pbn_scientist.lastName for p in response.context["problemy"])


@pytest.mark.parametrize(
    "slug,oczekiwane",
    [("2022-2025", ["Stary"]), ("2026-2030", ["Nowy"])],
)
def test_domyslny_zakres_lat_to_wybrany_okres(
    client_with_group, problemy, slug, oczekiwane
):
    """Bez ręcznego zakresu lista i pola „Rok od/do” biorą lata okresu
    z paska (dawniej zawsze 2022–2025)."""
    response = client_with_group.get(URL_OKRESU.format(slug=slug))

    assert response.status_code == 200
    assert _nazwiska(response) == oczekiwane
    rok_od, rok_do = slug.split("-")
    assert response.context["rok_min"] == rok_od
    assert response.context["rok_max"] == rok_do
    assert f"publikacje z lat {rok_od}–{rok_do}" in response.content.decode()


def test_bez_okresu_w_adresie_okres_domyslny(client_with_group, problemy):
    """Wejście bez okresu w adresie (np. test, skrypt): okres domyślny wg
    bieżącego roku, a nie lata wpisane na sztywno."""
    okres = okres_domyslny()

    response = client_with_group.get(URL)

    assert response.context["rok_min"] == str(okres.rok_od)
    assert response.context["rok_max"] == str(okres.rok_do)


def test_reczny_zakres_lat_ma_pierwszenstwo(client_with_group, problemy):
    """Strażnik: ręcznie wpisane lata działają jak dotąd, także szerzej niż
    okres; puste pola = bez ograniczenia."""
    url = URL_OKRESU.format(slug="2026-2030")

    response = client_with_group.get(url, {"rok_min": 2022, "rok_max": 2025})
    assert _nazwiska(response) == ["Stary"]

    response = client_with_group.get(url, {"rok_min": "", "rok_max": ""})
    assert _nazwiska(response) == ["Nowy", "Stary"]


def test_statystyki_licza_ten_sam_zakres_lat_co_lista(client_with_group, problemy):
    """Kafelki statystyk dotyczą tych samych lat co tabela (dawniej liczyły
    wszystkie lata, więc nie zgadzały się z listą)."""
    _brak_autora(2028, "Nowszy")

    response = client_with_group.get(URL_OKRESU.format(slug="2026-2030"))

    assert len(response.context["problemy"]) == 2
    assert response.context["total_count"] == 2
    assert response.context["brakujacy_total"] == 2
    assert response.context["missing_autor_count"] == 2

    response = client_with_group.get(URL_OKRESU.format(slug="2022-2025"))
    assert response.context["total_count"] == 1


def test_wyszukiwanie_po_tytule_nie_konczy_sie_bledem(client_with_group):
    """Pole „Szukaj” filtruje po tytule publikacji PBN, nazwisku i autorze
    (dawniej każde wyszukiwanie kończyło się błędem serwera)."""
    _brak_autora(2027, "Kowalski", tytul="Zielona energia")
    _brak_autora(2027, "Nowak", tytul="Czerwony kapturek")
    url = URL_OKRESU.format(slug="2026-2030")

    response = client_with_group.get(url, {"search": "zielona"})
    assert response.status_code == 200
    assert _nazwiska(response) == ["Kowalski"]

    response = client_with_group.get(url, {"search": "nowak"})
    assert _nazwiska(response) == ["Nowak"]


def test_pasek_okresu_na_liscie(client_with_group, problemy):
    """Na liście jest pasek wyboru okresu z linkami do obu okresów."""
    tresc = client_with_group.get(URL_OKRESU.format(slug="2026-2030")).content.decode()

    assert "pasek-okresu" in tresc
    assert 'href="/komparator-pbn-udzialy/2022-2025/"' in tresc


@pytest.mark.parametrize("adres", [URL, "/komparator-publikacji-pbn/"])
def test_wejscie_z_menu_przekierowuje_na_adres_z_okresem(admin_client, adres):
    """Nawigacja przeglądarki na adres bez okresu (link z górnego menu)
    trafia na adres z okresem domyślnym."""
    okres = okres_domyslny()

    response = admin_client.get(adres, headers={"Sec-Fetch-Mode": "navigate"})

    assert response.status_code == 302
    assert response["Location"] == f"{adres}{okres.slug}/"
