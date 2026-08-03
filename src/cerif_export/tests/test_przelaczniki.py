"""Przełączniki widoczności z obiektu ``Uczelnia``.

Dwa niezależne kill-switche, oba domyślnie WŁĄCZONE (istniejące wdrożenia
nie zmieniają zachowania):

* ``Uczelnia.api_v1_wlaczone`` — całe ``/api/v1/``,
* ``Uczelnia.eksport_cerif_wlaczony`` — endpoint OAI-PMH z CERIF-XML.

Wyłączony przełącznik daje **404**, nie 403/401 — endpoint ma wyglądać na
nieistniejący, a nie na „istnieje, ale nie dla ciebie".
"""

import pytest
from django.urls import NoReverseMatch, reverse

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


def _url_cerif():
    """URL endpointu OAI-PMH albo ``None``, gdy jeszcze nie istnieje.

    ``cerif_export/urls.py`` powstaje w Fazie 2 — do tego czasu testy
    przełącznika CERIF są pomijane (patrz ``skipif`` niżej).
    """
    try:
        return reverse("cerif_export:oai")
    except NoReverseMatch:
        return None


URL_CERIF = _url_cerif()

bez_endpointu_cerif = pytest.mark.skipif(
    URL_CERIF is None,
    reason="cerif_export:oai nie istnieje — endpoint powstaje w Fazie 2",
)


#
# /api/v1/ — Uczelnia.api_v1_wlaczone
#


def test_api_v1_wlaczone_domyslnie(uczelnia):
    """Default=True — wdrożenia sprzed wprowadzenia pola nic nie tracą."""
    assert uczelnia.api_v1_wlaczone is True


@pytest.mark.parametrize("nazwa_url", ENDPOINTY_API_V1)
def test_api_v1_domyslnie_odpowiada(client, uczelnia, nazwa_url):
    """Przy domyślnym ustawieniu bramka nie zmienia niczego: endpointy
    odpowiadają tak jak dotąd (200 publiczne, 401/403 wymagające konta) —
    byle nie 404, bo to sygnatura wyłączonego API."""
    res = client.get(reverse(nazwa_url))
    assert res.status_code != 404


@pytest.mark.parametrize("nazwa_url", ENDPOINTY_API_V1)
def test_api_v1_wylaczone_daje_404(client, uczelnia, nazwa_url):
    """Wyłączony przełącznik chowa CAŁE API — każdy endpoint daje 404."""
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    res = client.get(reverse(nazwa_url))
    assert res.status_code == 404


def test_api_v1_wylaczone_nie_daje_403_ani_401(client, uczelnia, admin_client):
    """Rozróżnienie jest istotne: 403/401 potwierdzałyby istnienie zasobu.

    Sprawdzane i dla anonima, i dla superusera — bramka nie jest kwestią
    uprawnień użytkownika, tylko istnienia endpointu.
    """
    uczelnia.api_v1_wlaczone = False
    uczelnia.save()

    url = reverse("api_v1:jednostka-list")
    for c in (client, admin_client):
        res = c.get(url)
        assert res.status_code == 404
        assert res.status_code not in (401, 403)


def test_api_v1_wylaczone_dziala_takze_na_detail(client, uczelnia, jednostka):
    """Bramka siedzi w ``has_permission``, więc łapie też widoki detalu —
    nie tylko listy."""
    url = reverse("api_v1:jednostka-detail", args=(jednostka.pk,))
    assert client.get(url).status_code == 200

    uczelnia.api_v1_wlaczone = False
    uczelnia.save()
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_api_v1_bez_uczelni_nie_jest_blokowane(client):
    """Brak obiektu ``Uczelnia`` (pusta baza, kreator konfiguracji) —
    nie ma kto podjąć decyzji, więc zachowujemy dotychczasowe zachowanie."""
    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 200


#
# CERIF — Uczelnia.eksport_cerif_wlaczony (odblokowuje się w Fazie 2)
#


def test_eksport_cerif_wlaczony_domyslnie(uczelnia):
    """Default=True — CERIF startuje aktywny."""
    assert uczelnia.eksport_cerif_wlaczony is True


@bez_endpointu_cerif
def test_cerif_domyslnie_odpowiada(client, uczelnia):
    res = client.get(URL_CERIF, {"verb": "Identify"})
    assert res.status_code == 200


@bez_endpointu_cerif
def test_cerif_wylaczony_daje_404(client, uczelnia):
    """Analogicznie do ``/api/v1/``: wyłączony eksport = endpoint nie
    istnieje (404), a nie „istnieje, ale odmawia" (403)."""
    uczelnia.eksport_cerif_wlaczony = False
    uczelnia.save()

    res = client.get(URL_CERIF, {"verb": "Identify"})
    assert res.status_code == 404


@pytest.mark.django_db
def test_endpoint_cerif_przyjmuje_post(uczelnia, settings):
    """OAI-PMH 2.0 wymaga POST — harvester nie ma tokenu CSRF.

    Regresja: bez ``csrf_exempt`` na widoku POST kończył się odpowiedzią
    403. Domyślny klient testowy Django nie wychwyciłby tego, bo omija
    sprawdzanie CSRF — stąd jawne ``enforce_csrf_checks``.
    """
    from django.test import Client

    settings.ALLOWED_HOSTS = ["*"]
    klient = Client(enforce_csrf_checks=True)

    odpowiedz = klient.post(
        reverse("cerif_export:oai"),
        {"verb": "Identify"},
        HTTP_HOST=uczelnia.site.domain,
    )

    assert odpowiedz.status_code == 200
    assert b"<Identify" in odpowiedz.content
