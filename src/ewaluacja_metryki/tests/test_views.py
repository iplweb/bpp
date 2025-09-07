from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker

from ewaluacja_metryki.models import MetrykaAutora, StatusGenerowania

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka


@pytest.mark.django_db
def test_metryki_list_view_requires_login(client):
    """Test że widok listy wymaga zalogowania"""
    url = reverse("ewaluacja_metryki:lista")
    response = client.get(url)

    # Powinno przekierować do logowania
    assert response.status_code == 302
    assert "/login/" in response.url or "/accounts/login/" in response.url


@pytest.mark.django_db
def test_metryki_list_view_logged_in(admin_user, client):
    """Test widoku listy dla zalogowanego użytkownika"""
    client.force_login(admin_user)

    # Stwórz dane testowe
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka")
    jednostka = baker.make(Jednostka, nazwa="Instytut Informatyki")

    metryka = baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.5"),
        punkty_nazbierane=Decimal("140.0"),
        slot_wszystkie=Decimal("4.0"),
        punkty_wszystkie=Decimal("150.0"),
        procent_wykorzystania_slotow=Decimal("87.5"),
    )

    url = reverse("ewaluacja_metryki:lista")
    response = client.get(url)

    assert response.status_code == 200
    assert "metryki" in response.context
    assert metryka in response.context["metryki"]
    assert b"Kowalski" in response.content
    assert b"Informatyka" in response.content


@pytest.mark.django_db
def test_metryki_list_view_filtering_by_nazwisko(admin_user, client):
    """Test filtrowania po nazwisku"""
    client.force_login(admin_user)

    autor1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor2 = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    metryka1 = baker.make(
        MetrykaAutora,
        autor=autor1,
        dyscyplina_naukowa=dyscyplina,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.0"),
        punkty_nazbierane=Decimal("120.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("120.0"),
    )
    metryka2 = baker.make(
        MetrykaAutora,
        autor=autor2,
        dyscyplina_naukowa=baker.make(Dyscyplina_Naukowa),
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.0"),
        punkty_nazbierane=Decimal("120.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("120.0"),
    )

    url = reverse("ewaluacja_metryki:lista")
    response = client.get(url, {"nazwisko": "Kowalski"})

    assert response.status_code == 200
    assert metryka1 in response.context["metryki"]
    assert metryka2 not in response.context["metryki"]


@pytest.mark.django_db
def test_metryki_list_view_filtering_by_jednostka(admin_user, client):
    """Test filtrowania po jednostce"""
    client.force_login(admin_user)

    jednostka1 = baker.make(Jednostka, nazwa="Instytut Informatyki")
    jednostka2 = baker.make(Jednostka, nazwa="Instytut Fizyki")

    metryka1 = baker.make(
        MetrykaAutora,
        jednostka=jednostka1,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.0"),
        punkty_nazbierane=Decimal("120.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("120.0"),
    )
    metryka2 = baker.make(
        MetrykaAutora,
        jednostka=jednostka2,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.0"),
        punkty_nazbierane=Decimal("120.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("120.0"),
    )

    url = reverse("ewaluacja_metryki:lista")
    response = client.get(url, {"jednostka": jednostka1.pk})

    assert response.status_code == 200
    assert metryka1 in response.context["metryki"]
    assert metryka2 not in response.context["metryki"]


@pytest.mark.django_db
def test_metryka_detail_view(admin_user, client):
    """Test widoku szczegółów metryki"""
    client.force_login(admin_user)

    metryka = baker.make(
        MetrykaAutora,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("3.5"),
        punkty_nazbierane=Decimal("140.0"),
        prace_nazbierane=[],
        slot_wszystkie=Decimal("4.0"),
        punkty_wszystkie=Decimal("150.0"),
        prace_wszystkie=[],
    )

    url = reverse("ewaluacja_metryki:szczegoly", kwargs={"pk": metryka.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["metryka"] == metryka
    assert "prace_nazbierane" in response.context
    assert "prace_wszystkie" in response.context


@pytest.mark.django_db
def test_statystyki_view(admin_user, client):
    """Test widoku statystyk"""
    client.force_login(admin_user)

    # Stwórz kilka metryk
    for i in range(5):
        baker.make(
            MetrykaAutora,
            slot_maksymalny=Decimal("4.0"),
            slot_nazbierany=Decimal(f"{3.0 + i * 0.2}"),
            punkty_nazbierane=Decimal(f"{120.0 + i * 10}"),
            slot_wszystkie=Decimal("4.0"),
            punkty_wszystkie=Decimal(f"{130.0 + i * 10}"),
            procent_wykorzystania_slotow=Decimal(f"{75.0 + i * 5}"),
        )

    url = reverse("ewaluacja_metryki:statystyki")
    response = client.get(url)

    assert response.status_code == 200
    assert "top_autorzy" in response.context
    assert "statystyki_globalne" in response.context
    assert "jednostki_stats" in response.context
    assert "dyscypliny_stats" in response.context
    assert "wykorzystanie_ranges" in response.context

    # Sprawdź statystyki globalne
    stats = response.context["statystyki_globalne"]
    assert stats["liczba_autorow"] == 5
    assert stats["srednia_wykorzystania"] is not None
    assert stats["srednia_pkd_slot"] is not None


@pytest.mark.django_db
def test_status_generowania_in_context(admin_user, client):
    """Test że status generowania jest w kontekście widoku listy"""
    client.force_login(admin_user)

    # Stwórz status
    status = StatusGenerowania.get_or_create()
    status.zakoncz_generowanie(liczba_przetworzonych=10, liczba_bledow=0)

    url = reverse("ewaluacja_metryki:lista")
    response = client.get(url)

    assert response.status_code == 200
    assert "status_generowania" in response.context
    assert response.context["status_generowania"] == status
    assert response.context["status_generowania"].liczba_przetworzonych == 10


@pytest.mark.django_db
def test_metryki_list_view_sorting(admin_user, client):
    """Test sortowania listy metryk"""
    client.force_login(admin_user)

    # Stwórz metryki z różnymi średnimi
    metryka1 = baker.make(
        MetrykaAutora,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("4.0"),
        punkty_nazbierane=Decimal("200.0"),  # średnia 50
        slot_wszystkie=Decimal("4.0"),
        punkty_wszystkie=Decimal("200.0"),
    )

    metryka2 = baker.make(
        MetrykaAutora,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("4.0"),
        punkty_nazbierane=Decimal("120.0"),  # średnia 30
        slot_wszystkie=Decimal("4.0"),
        punkty_wszystkie=Decimal("120.0"),
    )

    url = reverse("ewaluacja_metryki:lista")

    # Domyślne sortowanie - malejąco po średniej
    response = client.get(url)
    assert response.status_code == 200
    metryki_list = list(response.context["metryki"])
    assert metryki_list[0] == metryka1  # Wyższa średnia pierwsza
    assert metryki_list[1] == metryka2

    # Sortowanie rosnąco po średniej
    response = client.get(url, {"sort": "srednia_za_slot_nazbierana"})
    assert response.status_code == 200
    metryki_list = list(response.context["metryki"])
    assert metryki_list[0] == metryka2  # Niższa średnia pierwsza
    assert metryki_list[1] == metryka1
