import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models.profile import BppUser


@pytest.mark.django_db
def test_views_require_group_permission(client):
    """Test że widoki wymagają grupy GR_WPROWADZANIE_DANYCH"""

    # Utwórz użytkownika bez uprawnień
    user = baker.make(BppUser, username="test_user")
    user.set_password("test_password")
    user.save()

    client.login(username="test_user", password="test_password")

    # Sprawdź że widoki są niedostępne
    urls_to_test = [
        reverse("ewaluacja_metryki:lista"),
        reverse("ewaluacja_metryki:statystyki"),
        reverse("ewaluacja_metryki:uruchom_generowanie"),
        reverse("ewaluacja_metryki:status_generowania"),
    ]

    for url in urls_to_test:
        response = client.get(url)
        # Powinno przekierować lub zwrócić 403
        assert response.status_code in [302, 403], f"URL {url} powinien być niedostępny"


@pytest.mark.django_db
def test_views_accessible_with_group(client):
    """Test że widoki są dostępne dla użytkowników z grupą GR_WPROWADZANIE_DANYCH"""

    # Utwórz grupę i użytkownika
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user = baker.make(BppUser, username="test_user_with_group")
    user.set_password("test_password")
    user.groups.add(group)
    user.save()

    client.login(username="test_user_with_group", password="test_password")

    # Sprawdź że lista jest dostępna
    url = reverse("ewaluacja_metryki:lista")
    response = client.get(url)
    assert response.status_code == 200

    # Sprawdź że statystyki są dostępne
    url = reverse("ewaluacja_metryki:statystyki")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_views_accessible_for_superuser(client):
    """Test że widoki są dostępne dla superusera"""

    # Utwórz superusera
    user = baker.make(BppUser, username="superuser", is_superuser=True)
    user.set_password("test_password")
    user.save()

    client.login(username="superuser", password="test_password")

    # Sprawdź że lista jest dostępna
    url = reverse("ewaluacja_metryki:lista")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_generation_requires_staff(client):
    """Test że uruchamianie generowania wymaga dodatkowo uprawnień staff"""

    # Utwórz użytkownika z grupą ale bez staff
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user = baker.make(BppUser, username="user_no_staff", is_staff=False)
    user.set_password("test_password")
    user.groups.add(group)
    user.save()

    client.login(username="user_no_staff", password="test_password")

    # Próba uruchomienia generowania
    url = reverse("ewaluacja_metryki:uruchom_generowanie")
    response = client.post(
        url, {"rok_min": 2022, "rok_max": 2025, "minimalny_pk": 0.01, "nadpisz": "on"}
    )

    # Powinno przekierować z komunikatem o braku uprawnień
    assert response.status_code == 302

    # Teraz z uprawnieniami staff
    user.is_staff = True
    user.save()

    from ewaluacja_metryki.models import StatusGenerowania

    status = StatusGenerowania.get_or_create()
    status.w_trakcie = False
    status.save()

    # Mockuj task
    from unittest.mock import MagicMock, patch

    with patch("ewaluacja_metryki.views.generuj_metryki_task") as mock_task:
        mock_task.delay.return_value = MagicMock(id="test-task-id")

        response = client.post(
            url,
            {"rok_min": 2022, "rok_max": 2025, "minimalny_pk": 0.01, "nadpisz": "on"},
        )

        # Teraz powinno działać
        assert response.status_code == 302
        mock_task.delay.assert_called_once()


@pytest.mark.django_db
def test_breadcrumbs_in_templates(client, admin_user):
    """Test że breadcrumbs są poprawnie wyświetlane"""

    # Dodaj grupę do admin_user
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    admin_user.groups.add(group)

    client.force_login(admin_user)

    # Test listy
    response = client.get(reverse("ewaluacja_metryki:lista"))
    assert response.status_code == 200
    assert b"Strona" in response.content
    assert b"Metryki ewaluacyjne" in response.content

    # Test statystyk
    response = client.get(reverse("ewaluacja_metryki:statystyki"))
    assert response.status_code == 200
    assert b"Strona" in response.content
    assert b"Metryki ewaluacyjne" in response.content
    assert b"Statystyki" in response.content
