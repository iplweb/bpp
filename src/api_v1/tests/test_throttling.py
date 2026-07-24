"""Testy throttlingu kosztownych endpointów wyszukiwania (#6 z security review).

Globalny throttling jest wyłączony — limitujemy tylko ``/szukaj/`` i ``/autor/``.
"""

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from api_v1.throttling import SearchAnonThrottle, SearchUserThrottle
from api_v1.viewsets.autor import AutorViewSet
from api_v1.viewsets.szukaj import SzukajViewSet

# LocMemCache — throttle liczy requesty realnie (DummyCache byłby no-op).
_LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "throttle-test",
    }
}

# DRF wiąże ``SimpleRateThrottle.THROTTLE_RATES`` jako atrybut klasy w czasie
# importu (w prod OK — rate'y ustawione w settings przed importem; nie zmieniają
# się). override_settings tego nie sięga, więc w teście zaniżamy limit wprost na
# klasach throttle przez monkeypatch.
_RATES_LOW = {"search_anon": "2/min", "search_user": "1000/min"}


@pytest.fixture
def niski_limit_wyszukiwania(monkeypatch):
    monkeypatch.setattr(SearchAnonThrottle, "THROTTLE_RATES", _RATES_LOW)
    monkeypatch.setattr(SearchUserThrottle, "THROTTLE_RATES", _RATES_LOW)


def test_search_viewsets_deklaruja_throttle_wyszukiwania():
    """Opt-in: kosztowne endpointy mają rozdzielne throttle anon/user."""
    assert SzukajViewSet.throttle_classes == [SearchAnonThrottle, SearchUserThrottle]
    assert AutorViewSet.throttle_classes == [SearchAnonThrottle, SearchUserThrottle]


def test_zapytanie_viewsety_deklaruja_throttle_uzytkownika():
    """DjangoQL po API (``/api/v1/zapytanie/*``) to ciężki multi-join —
    endpointy wymagają logowania, więc throttle po użytkowniku wystarcza."""
    from api_v1.viewsets.zapytanie import ZapytanieAPIBaseViewSet

    assert ZapytanieAPIBaseViewSet.throttle_classes == [SearchUserThrottle]


@override_settings(CACHES=_LOCMEM)
@pytest.mark.django_db
def test_zapytanie_throttluje_zalogowanego_po_przekroczeniu_limitu(monkeypatch):
    from model_bakery import baker
    from rest_framework.test import APIClient

    monkeypatch.setattr(
        SearchUserThrottle,
        "THROTTLE_RATES",
        {"search_user": "2/min", "search_anon": "60/min"},
    )
    cache.clear()

    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=u)
    url = "/api/v1/zapytanie/autor/"
    params = {"q": 'nazwisko ~ "x"'}

    assert client.get(url, params).status_code == 200
    assert client.get(url, params).status_code == 200
    # Trzecie wywołanie przekracza limit 2/min → 429 Too Many Requests.
    assert client.get(url, params).status_code == 429


@override_settings(CACHES=_LOCMEM)
@pytest.mark.django_db
def test_szukaj_throttluje_anonima_po_przekroczeniu_limitu(
    api_client, niski_limit_wyszukiwania
):
    cache.clear()
    url = reverse("api_v1:szukaj-list")

    assert api_client.get(url).status_code == 200
    assert api_client.get(url).status_code == 200
    # Trzecie wywołanie przekracza limit 2/min → 429 Too Many Requests.
    assert api_client.get(url).status_code == 429


@override_settings(CACHES=_LOCMEM)
@pytest.mark.django_db
def test_autor_throttluje_anonima_po_przekroczeniu_limitu(
    api_client, niski_limit_wyszukiwania
):
    cache.clear()
    url = reverse("api_v1:autor-list")

    assert api_client.get(url).status_code == 200
    assert api_client.get(url).status_code == 200
    assert api_client.get(url).status_code == 429


@override_settings(CACHES=_LOCMEM)
@pytest.mark.django_db
def test_inne_endpointy_bez_throttlingu(api_client, monkeypatch):
    """Endpoint spoza wyszukiwania (np. /jezyk/) NIE jest limitowany —
    globalny throttling pozostaje wyłączony (nawet przy skrajnie niskim
    limicie wyszukiwania)."""
    monkeypatch.setattr(SearchAnonThrottle, "THROTTLE_RATES", {"search_anon": "1/min"})
    cache.clear()
    url = reverse("api_v1:jezyk-list")
    for _ in range(4):
        assert api_client.get(url).status_code == 200
