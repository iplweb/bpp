"""
Testy widoków listowania źródeł w aplikacji przemapuj_zrodla_pbn.

Ten moduł zawiera testy dla:
- ListaSkasowanychZrodelView - widok listy źródeł ze statusem DELETED w PBN
"""

import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_lista_skasowanych_zrodel_view_requires_login(client):
    """Test czy widok wymaga zalogowania"""
    url = reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")
    response = client.get(url)

    # Powinno przekierować na login
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_lista_skasowanych_zrodel_view_shows_deleted_sources(client, django_user_model):
    """Test czy widok pokazuje źródła ze statusem DELETED"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Utwórz źródło ze statusem DELETED
    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Skasowana Gazeta",
        issn="",
        eissn="",
        websiteLink="",
    )
    baker.make("bpp.Zrodlo", nazwa="Skasowana Gazeta", pbn_uid=journal_deleted)

    # Utwórz źródło ze statusem ACTIVE (nie powinno się pojawić)
    journal_active = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Aktywna Gazeta",
        issn="",
        eissn="",
        websiteLink="",
    )
    baker.make("bpp.Zrodlo", nazwa="Aktywna Gazeta", pbn_uid=journal_active)

    url = reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")
    response = client.get(url)

    assert response.status_code == 200
    assert "Skasowana Gazeta" in response.content.decode()
    assert "Aktywna Gazeta" not in response.content.decode()


@pytest.mark.django_db
def test_lista_skasowanych_zrodel_shows_usun_button_for_zero_records(
    client, django_user_model
):
    """Test czy lista pokazuje przycisk 'Usuń' dla źródeł bez rekordów"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Źródło bez rekordów
    journal_deleted_empty = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Pusta Gazeta",
        issn="",
        eissn="",
        websiteLink="",
    )
    baker.make("bpp.Zrodlo", nazwa="Pusta Gazeta", pbn_uid=journal_deleted_empty)

    # Źródło z rekordami
    journal_deleted_with_records = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Gazeta z Rekordami",
        issn="",
        eissn="",
        websiteLink="",
    )
    zrodlo_with_records = baker.make(
        "bpp.Zrodlo", nazwa="Gazeta z Rekordami", pbn_uid=journal_deleted_with_records
    )
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo_with_records)

    url = reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Sprawdź czy jest przycisk "Usuń" dla pustej gazety
    assert "Pusta Gazeta" in content
    assert content.count("fi-trash") >= 1  # Ikona kosza

    # Sprawdź czy jest przycisk "Przemapuj" dla gazety z rekordami
    assert "Gazeta z Rekordami" in content
    assert content.count("fi-refresh") >= 1  # Ikona odświeżania
