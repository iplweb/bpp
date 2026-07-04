"""Testy endpointu JSON zwracającego detale pojedynczego źródła.

Endpoint zasila prawy panel „Źródło docelowe" na stronie przemapowania:
po zmianie comboboxa JS fetchuje `przemapuj_zrodlo:info` i wypełnia panel
tymi samymi parametrami co panel źródłowy (ISSN, PBN UID, MNiSW ID,
liczba publikacji).
"""

import json

import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_zrodlo_info_returns_json(client_with_group):
    """Endpoint zwraca komplet parametrów źródła + liczbę publikacji."""
    from pbn_api.models import Journal

    journal = baker.make(Journal, mniswId=12345, status="CURRENT", title="J")
    zrodlo = baker.make(
        "bpp.Zrodlo",
        nazwa="Docelowe",
        skrot="Doc.",
        issn="1234-5678",
        e_issn="8765-4321",
        pbn_uid=journal,
    )
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, _quantity=3)

    url = reverse("przemapuj_zrodlo:info", args=[zrodlo.pk])
    response = client_with_group.get(url)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["bppid"] == zrodlo.pk
    assert data["nazwa"] == "Docelowe"
    assert data["skrot"] == "Doc."
    assert data["issn"] == "1234-5678"
    assert data["e_issn"] == "8765-4321"
    assert data["pbn_uid_id"] == journal.pk
    assert data["mniswId"] == 12345
    assert data["pbn_status"] == "CURRENT"
    assert data["mnisw_effective"] == 12345
    assert data["liczba_publikacji"] == 3


@pytest.mark.django_db
def test_zrodlo_info_bez_pbn(client_with_group):
    """Źródło bez odpowiednika w PBN — pola PBN/MNiSW są null, nie wysypuje się."""
    zrodlo = baker.make("bpp.Zrodlo", nazwa="Bez PBN", issn="", e_issn="")

    url = reverse("przemapuj_zrodlo:info", args=[zrodlo.pk])
    response = client_with_group.get(url)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["pbn_uid_id"] is None
    assert data["mniswId"] is None
    assert data["pbn_status"] is None
    assert data["mnisw_effective"] is None
    assert data["liczba_publikacji"] == 0


@pytest.mark.django_db
def test_zrodlo_info_deleted_mnisw_effective_is_none(client_with_group):
    """Dla źródła ministerialnego usuniętego z PBN (status DELETED) surowe
    mniswId nadal jest pokazywane, ale `mnisw_effective` (używane do reguły
    blokady) jest None — bo taka reguła obowiązuje w walidacji formularza."""
    from pbn_api.models import Journal

    journal = baker.make(Journal, mniswId=777, status="DELETED", title="Del")
    zrodlo = baker.make("bpp.Zrodlo", pbn_uid=journal)

    url = reverse("przemapuj_zrodlo:info", args=[zrodlo.pk])
    data = json.loads(client_with_group.get(url).content)

    assert data["mniswId"] == 777
    assert data["pbn_status"] == "DELETED"
    assert data["mnisw_effective"] is None


@pytest.mark.django_db
def test_zrodlo_info_404_for_missing(client_with_group):
    """Nieistniejące źródło → 404."""
    url = reverse("przemapuj_zrodlo:info", args=[999999])
    response = client_with_group.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_zrodlo_info_requires_permission(client):
    """Anonimowy użytkownik nie dostaje danych źródła."""
    zrodlo = baker.make("bpp.Zrodlo")
    url = reverse("przemapuj_zrodlo:info", args=[zrodlo.pk])
    response = client.get(url)
    assert response.status_code in [302, 403]
