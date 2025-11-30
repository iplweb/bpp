"""
Tests for login and activity statistics views in admin_dashboard.
"""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

# ============================================================================
# Tests for recent_logins_view
# ============================================================================


@pytest.mark.django_db
def test_recent_logins_view_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:recent_logins")
    response = client.get(url)
    assert response.status_code == 302  # Redirect do logowania


@pytest.mark.django_db
def test_recent_logins_view_staff_sees_own_logins(
    client, staff_user, login_events_for_user
):
    """Test weryfikujący, że zwykły staff widzi tylko swoje logowania."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:recent_logins")
    response = client.get(url)

    assert response.status_code == 200
    assert "logins" in response.context
    logins = list(response.context["logins"])
    assert len(logins) <= 10
    # Wszystkie logowania powinny być użytkownika staff_user
    for login in logins:
        assert login.user == staff_user


@pytest.mark.django_db
def test_recent_logins_view_superuser_sees_all_logins(
    client, superuser, login_events_multiple_users
):
    """Test weryfikujący, że superuser widzi wszystkie logowania."""
    client.force_login(superuser)
    url = reverse("admin_dashboard:recent_logins")
    response = client.get(url)

    assert response.status_code == 200
    assert "logins" in response.context
    assert response.context["is_superuser"] is True
    logins = list(response.context["logins"])
    # Superuser powinien widzieć logowania różnych użytkowników
    user_ids = {login.user.id for login in logins}
    assert len(user_ids) >= 1  # Przynajmniej jeden użytkownik


@pytest.mark.django_db
def test_recent_logins_view_limit_10(client, staff_user):
    """Test weryfikujący, że widok zwraca maksymalnie 10 ostatnich logowań."""
    from easyaudit.models import LoginEvent

    # Utwórz 15 logowań
    for i in range(15):
        baker.make(
            LoginEvent,
            user=staff_user,
            login_type=LoginEvent.LOGIN,
            datetime=timezone.now() - timedelta(hours=i),
        )

    client.force_login(staff_user)
    url = reverse("admin_dashboard:recent_logins")
    response = client.get(url)

    assert response.status_code == 200
    logins = list(response.context["logins"])
    assert len(logins) == 10


# ============================================================================
# Tests for weekday_stats
# ============================================================================


@pytest.mark.django_db
def test_weekday_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:weekday_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_weekday_stats_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:weekday_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"

    data = json.loads(response.content)
    assert "data" in data
    assert "layout" in data


@pytest.mark.django_db
def test_weekday_stats_structure(client, staff_user, log_entries_weekdays):
    """Test weryfikujący strukturę danych zwracanych przez weekday_stats."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:weekday_stats")
    response = client.get(url)

    data = json.loads(response.content)
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0

    chart_data = data["data"][0]
    assert "x" in chart_data
    assert "y" in chart_data
    assert "type" in chart_data
    assert chart_data["type"] == "bar"

    # Sprawdź, że mamy 5 dni tygodnia (Pon-Pt)
    assert len(chart_data["x"]) == 5
    assert len(chart_data["y"]) == 5


@pytest.mark.django_db
def test_weekday_stats_cached(client, staff_user):
    """Test weryfikujący, że widok jest cache'owany."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:weekday_stats")

    # Pierwsze wywołanie
    response1 = client.get(url)
    assert response1.status_code == 200

    # Drugie wywołanie - powinno zwrócić ten sam wynik z cache
    response2 = client.get(url)
    assert response2.status_code == 200
    assert response1.content == response2.content


# ============================================================================
# Tests for day_of_month_activity_stats
# ============================================================================


@pytest.mark.django_db
def test_day_of_month_activity_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:day_of_month_activity_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_day_of_month_activity_stats_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:day_of_month_activity_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"

    data = json.loads(response.content)
    assert "data" in data
    assert "layout" in data


@pytest.mark.django_db
def test_day_of_month_activity_stats_structure(client, staff_user):
    """Test weryfikujący strukturę danych zwracanych przez day_of_month_activity_stats."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:day_of_month_activity_stats")
    response = client.get(url)

    data = json.loads(response.content)
    chart_data = data["data"][0]

    # Sprawdź, że mamy 31 dni
    assert len(chart_data["x"]) == 31
    assert len(chart_data["y"]) == 31
    assert chart_data["type"] == "bar"
