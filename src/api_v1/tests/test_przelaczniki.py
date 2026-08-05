"""Przełączniki konfiguracyjne REST API ``/api/v1/`` na obiekcie ``Uczelnia``.

Sześć pól: główny wyłącznik, ograniczenie do zalogowanych i cztery grupy
endpointów. Wszystkie defaulty zachowują dotychczasowe zachowanie — jedyne
domyślnie wyłączone to ograniczenie do zalogowanych.
"""

import pytest
from django.urls import reverse

from api_v1.permissions import (
    KOMUNIKAT_GLOWNY,
    KOMUNIKAT_GRUPA,
    KOMUNIKAT_ZALOGOWANI,
)

from bpp.models import Uczelnia
from bpp.models.uczelnia import GrupaApiV1

# Po jednym reprezentatywnym endpoincie z każdej grupy. Kafelki mają własne
# testy niżej, bo są jedynym wyjątkiem od hierarchii przełączników.
ENDPOINT_GRUPY = {
    GrupaApiV1.DANE_BIBLIOGRAFICZNE: "api_v1:jednostka-list",
    GrupaApiV1.WYSZUKIWANIE: "api_v1:szukaj-list",
    GrupaApiV1.NARZEDZIA_REDAKTORSKIE: "api_v1:zapytanie_rekord-list",
}

NAGLOWEK_CORS = "Access-Control-Allow-Origin"


def url_kafelka_autora(autor):
    return reverse("api_v1:recent_author_publications-detail", args=(autor.pk,))


def test_defaulty_zachowuja_obecne_zachowanie(uczelnia):
    """Wdrożenie sprzed tej zmiany nie traci żadnej funkcji."""
    assert uczelnia.api_v1_wlaczone is True
    assert uczelnia.api_v1_dane_bibliograficzne is True
    assert uczelnia.api_v1_wyszukiwanie is True
    assert uczelnia.api_v1_kafelki is True
    assert uczelnia.api_v1_narzedzia_redaktorskie is True


def test_tylko_zalogowani_domyslnie_wylaczone(uczelnia):
    """Jedyne pole, którego włączenie zmienia zachowanie — więc domyślnie
    wyłączone."""
    assert uczelnia.api_v1_tylko_zalogowani is False


@pytest.mark.parametrize("grupa", list(GrupaApiV1))
def test_kazda_grupa_ma_pole_na_uczelni(grupa):
    """Wartość enuma jest sufiksem nazwy pola (``api_v1_<value>``).

    Wiązanie idzie przez ``getattr``, więc nie ma kontroli statycznej —
    literówka w enumie wybuchłaby dopiero na produkcji, przy pierwszym
    żądaniu do danej grupy.
    """
    assert hasattr(Uczelnia, f"api_v1_{grupa.value}")


@pytest.mark.parametrize("grupa", list(GrupaApiV1))
def test_api_v1_grupa_wlaczona_czyta_wlasciwe_pole(uczelnia, grupa):
    assert uczelnia.api_v1_grupa_wlaczona(grupa) is True

    setattr(uczelnia, f"api_v1_{grupa.value}", False)
    assert uczelnia.api_v1_grupa_wlaczona(grupa) is False


#
# Bramka: grupy endpointów
#


@pytest.mark.parametrize("grupa,nazwa_url", list(ENDPOINT_GRUPY.items()))
def test_grupa_wlaczona_endpoint_istnieje(client, uczelnia, grupa, nazwa_url):
    """Domyślnie bramka nie zmienia niczego — byle nie 404, bo to sygnatura
    wyłączonego endpointu."""
    assert client.get(reverse(nazwa_url)).status_code != 404


@pytest.mark.parametrize("grupa,nazwa_url", list(ENDPOINT_GRUPY.items()))
def test_grupa_wylaczona_daje_404(client, uczelnia, grupa, nazwa_url):
    setattr(uczelnia, f"api_v1_{grupa.value}", False)
    uczelnia.save()

    res = client.get(reverse(nazwa_url))
    assert res.status_code == 404
    assert res.json()["powod"] == "grupa_wylaczona"
    assert res.json()["grupa"] == grupa.value
    assert res.json()["detail"] == KOMUNIKAT_GRUPA


def test_wylaczenie_grupy_nie_rusza_pozostalych(client, uczelnia):
    """Regresja w mapowaniu prefiks→grupa inaczej przeszłaby niezauważona."""
    uczelnia.api_v1_wyszukiwanie = False
    uczelnia.save()

    assert client.get(reverse("api_v1:szukaj-list")).status_code == 404
    assert client.get(reverse("api_v1:jednostka-list")).status_code == 200


#
# Bramka: główny wyłącznik
#


def test_glowny_wylacznik_daje_404_z_powodem(client, uczelnia):
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 404
    assert res.json()["powod"] == "api_wylaczone"
    assert res.json()["detail"] == KOMUNIKAT_GLOWNY


def test_glowny_wylacznik_dziala_takze_na_detail(client, uczelnia, jednostka):
    """Bramka siedzi w ``has_permission``, więc łapie też widoki detalu."""
    url = reverse("api_v1:jednostka-detail", args=(jednostka.pk,))
    assert client.get(url).status_code == 200

    uczelnia.api_v1_wlaczone = False
    uczelnia.save()
    assert client.get(url).status_code == 404


def test_glowny_wylacznik_daje_404_takze_superuserowi(
    client, admin_client, uczelnia
):
    """Bramka nie jest kwestią uprawnień użytkownika, tylko istnienia
    endpointu — więc superuser widzi to samo, co anonim."""
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    url = reverse("api_v1:jednostka-list")
    for c in (client, admin_client):
        assert c.get(url).status_code == 404


#
# Bramka: ograniczenie do zalogowanych
#


def test_tylko_zalogowani_anonim_dostaje_401(client, uczelnia):
    """401, nie 403 — kontrakt whoami/ dla bpp-mcp (spec §5.4d) wymaga kodu
    mapowalnego na ponowne logowanie. PermissionDenied dałby 403."""
    uczelnia.api_v1_tylko_zalogowani = True
    uczelnia.save()

    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 401
    assert res.has_header("WWW-Authenticate")
    assert res.json()["powod"] == "wymagane_zalogowanie"
    assert res.json()["detail"] == KOMUNIKAT_ZALOGOWANI


def test_tylko_zalogowani_zalogowany_widzi_dane(admin_client, uczelnia):
    uczelnia.api_v1_tylko_zalogowani = True
    uczelnia.save()

    assert admin_client.get(reverse("api_v1:jednostka-list")).status_code == 200


#
# Kafelki do osadzania — jedyne złamanie hierarchii
#


def test_kafelki_zyja_mimo_wylaczonego_api(client, uczelnia, autor_jan_nowak):
    """Widget wisi na publicznych stronach WWW jednostek, których
    administrator BPP nie kontroluje — wyłączenie API nie może po cichu
    psuć cudzych stron."""
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    assert client.get(url_kafelka_autora(autor_jan_nowak)).status_code == 200


def test_kafelki_zyja_mimo_tylko_zalogowanych(client, uczelnia, autor_jan_nowak):
    uczelnia.api_v1_tylko_zalogowani = True
    uczelnia.save()

    assert client.get(url_kafelka_autora(autor_jan_nowak)).status_code == 200


def test_kafelki_wylaczone_daja_404_z_powodem(client, uczelnia, autor_jan_nowak):
    uczelnia.api_v1_kafelki = False
    uczelnia.save()

    res = client.get(url_kafelka_autora(autor_jan_nowak))
    assert res.status_code == 404
    assert res.json()["powod"] == "grupa_wylaczona"
    assert res.json()["grupa"] == GrupaApiV1.KAFELKI.value


def test_404_encji_nie_ma_klucza_powod(client, uczelnia):
    """Druga połowa kontraktu: 404 z ``pobierz_encje_lub_404`` NIE jest
    decyzją administratora, więc widget ma go pokazać, a nie wyciszyć."""
    url = reverse("api_v1:recent_author_publications-detail", args=(99999999,))
    res = client.get(url)
    assert res.status_code == 404
    assert "powod" not in res.json()


#
# Kontrakt routera
#


def test_rejestracja_bez_grupy_jest_bledem():
    """Wartość domyślna po cichu odtworzyłaby furtkę przy każdym nowym
    viewsecie — dlatego ``grupa`` jest keyword-only bez defaultu."""
    from api_v1.urls import CustomRouter
    from api_v1.viewsets.struktura import JednostkaViewSet

    router = CustomRouter()
    with pytest.raises(TypeError):
        router.register(r"test", JednostkaViewSet, basename="test_bez_grupy")


#
# Listing korzenia /api/v1/
#


def test_root_ukrywa_endpointy_wylaczonych_grup(client, uczelnia):
    """Bez filtra listing reklamowałby adresy prowadzące prosto w 404."""
    dane = client.get(reverse("api_v1:api-root")).json()
    assert "jednostka" in dane["authors_and_units"]

    uczelnia.api_v1_dane_bibliograficzne = False
    uczelnia.save()

    dane = client.get(reverse("api_v1:api-root")).json()
    assert "authors_and_units" not in dane
    assert "publications" not in dane
    assert "info" in dane


def test_root_przy_wszystkich_grupach_wylaczonych_zwraca_samo_info(client, uczelnia):
    uczelnia.api_v1_dane_bibliograficzne = False
    uczelnia.api_v1_wyszukiwanie = False
    uczelnia.api_v1_kafelki = False
    uczelnia.api_v1_narzedzia_redaktorskie = False
    uczelnia.save()

    res = client.get(reverse("api_v1:api-root"))
    assert res.status_code == 200
    assert list(res.json().keys()) == ["info"]


def test_root_i_whoami_ida_za_glownym_wylacznikiem(client, uczelnia):
    """Jedyne dwa widoki bez grupy — łatwo je pominąć przy refaktorze."""
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    for nazwa in ("api_v1:api-root", "api_v1:whoami"):
        res = client.get(reverse(nazwa))
        assert res.status_code == 404, nazwa
        assert res.json()["powod"] == "api_wylaczone", nazwa


def test_root_i_whoami_nie_zalezy_od_grup(client, uczelnia):
    uczelnia.api_v1_dane_bibliograficzne = False
    uczelnia.save()

    assert client.get(reverse("api_v1:api-root")).status_code == 200
    # whoami wymaga konta (IsAuthenticated), więc anonim dostaje 401 —
    # istotne jest, że to NIE jest 404 od bramki.
    assert client.get(reverse("api_v1:whoami")).status_code != 404


#
# CORS na odpowiedziach błędów endpointów kafelkowych
#


def test_cors_na_404_z_bramki(client, uczelnia, autor_jan_nowak):
    """Bez tego nagłówka przeglądarka nie poda odpowiedzi skryptowi na cudzej
    domenie — ``fetch`` odrzuca się bez statusu i bez treści, więc widget
    nigdy nie zobaczy klucza ``powod``."""
    uczelnia.api_v1_kafelki = False
    uczelnia.save()

    res = client.get(url_kafelka_autora(autor_jan_nowak))
    assert res.status_code == 404
    assert res[NAGLOWEK_CORS] == "*"


def test_cors_na_404_nieistniejacej_encji(client, uczelnia):
    url = reverse("api_v1:recent_author_publications-detail", args=(99999999,))
    res = client.get(url)
    assert res.status_code == 404
    assert res[NAGLOWEK_CORS] == "*"


def test_cors_na_404_nieistniejacej_jednostki(client, uczelnia):
    url = reverse("api_v1:recent_unit_publications-detail", args=(99999999,))
    res = client.get(url)
    assert res.status_code == 404
    assert res[NAGLOWEK_CORS] == "*"


def test_cors_nadal_na_odpowiedzi_sukcesu(client, uczelnia, autor_jan_nowak):
    res = client.get(url_kafelka_autora(autor_jan_nowak))
    assert res.status_code == 200
    assert res[NAGLOWEK_CORS] == "*"


#
# Przeniesione z src/cerif_export/tests/test_przelaczniki.py — testy
# przełącznika /api/v1/ powstały razem ze specyfikacją eksportu CERIF
# i mieszkały w tamtej aplikacji z przyczyn czysto historycznych.
#

# Endpointy reprezentatywne dla różnych rodzajów widoków pod /api/v1/:
# korzeń routera, zwykły ModelViewSet, viewset z własnymi
# ``permission_classes`` oraz widok spoza routera (``whoami``).
ENDPOINTY_API_V1 = [
    "api_v1:api-root",
    "api_v1:jednostka-list",
    "api_v1:autor-list",
    "api_v1:zapytanie_rekord-list",
    "api_v1:whoami",
]


@pytest.mark.parametrize("nazwa_url", ENDPOINTY_API_V1)
def test_api_v1_domyslnie_odpowiada(client, uczelnia, nazwa_url):
    """Przy domyślnym ustawieniu bramka nie zmienia niczego: endpointy
    odpowiadają tak jak dotąd (200 publiczne, 401 wymagające konta) —
    byle nie 404, bo to sygnatura wyłączonego API."""
    res = client.get(reverse(nazwa_url))
    assert res.status_code != 404


@pytest.mark.parametrize("nazwa_url", ENDPOINTY_API_V1)
def test_api_v1_wylaczone_daje_404(client, uczelnia, nazwa_url):
    """Wyłączony główny przełącznik chowa CAŁE API — każdy endpoint daje 404.

    Kafelki są jedynym wyjątkiem i mają własne testy wyżej.
    """
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    assert client.get(reverse(nazwa_url)).status_code == 404


@pytest.mark.django_db
def test_api_v1_bez_uczelni_nie_jest_blokowane(client):
    """Brak obiektu ``Uczelnia`` (pusta baza, kreator konfiguracji) — nie ma
    kto podjąć decyzji, więc zachowujemy dotychczasowe zachowanie."""
    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 200
