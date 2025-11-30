"""
Tests for publication statistics views in admin_dashboard.
"""

import json

import pytest
from django.urls import reverse

from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

# ============================================================================
# Tests for new_publications_stats
# ============================================================================


@pytest.mark.django_db
def test_new_publications_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:new_publications_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_new_publications_stats_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:new_publications_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_new_publications_stats_structure(client, staff_user, publications_with_years):
    """Test weryfikujący strukturę danych zwracanych przez new_publications_stats."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:new_publications_stats")
    response = client.get(url)

    data = json.loads(response.content)
    assert "data" in data
    assert "layout" in data
    assert isinstance(data["data"], list)

    # Powinny być 2 serie danych - ciągłe i zwarte
    assert len(data["data"]) == 2

    for series in data["data"]:
        assert "x" in series
        assert "y" in series
        assert "type" in series
        assert series["type"] == "scatter"
        assert series["mode"] == "lines"


@pytest.mark.django_db
def test_new_publications_stats_handles_models_without_utworzono(
    client, staff_user, monkeypatch
):
    """Test weryfikujący, że widok obsługuje modele bez pola utworzono."""
    # Symuluj brak atrybutu utworzono
    monkeypatch.delattr(Wydawnictwo_Ciagle, "utworzono", raising=False)
    monkeypatch.delattr(Wydawnictwo_Zwarte, "utworzono", raising=False)

    client.force_login(staff_user)
    url = reverse("admin_dashboard:new_publications_stats")
    response = client.get(url)

    assert response.status_code == 200
    data = json.loads(response.content)
    # Powinien zwrócić puste dane
    assert len(data["data"]) == 2
    for series in data["data"]:
        assert len(series["x"]) == 0


# ============================================================================
# Tests for cumulative_publications_stats
# ============================================================================


@pytest.mark.django_db
def test_cumulative_publications_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:cumulative_publications_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_cumulative_publications_stats_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:cumulative_publications_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_cumulative_publications_stats_structure(
    client, staff_user, publications_with_years
):
    """Test weryfikujący strukturę danych zwracanych przez cumulative_publications_stats."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:cumulative_publications_stats")
    response = client.get(url)

    data = json.loads(response.content)
    assert "data" in data
    assert "layout" in data

    if len(data["data"]) > 0:
        chart_data = data["data"][0]
        assert "x" in chart_data
        assert "y" in chart_data
        assert chart_data["type"] == "scatter"
        assert chart_data["mode"] == "lines"
        assert "fill" in chart_data


@pytest.mark.django_db
def test_cumulative_publications_stats_empty_database(client, staff_user):
    """Test weryfikujący, że widok obsługuje pustą bazę danych."""
    # Usuń wszystkie publikacje
    Wydawnictwo_Ciagle.objects.all().delete()
    Wydawnictwo_Zwarte.objects.all().delete()

    client.force_login(staff_user)
    url = reverse("admin_dashboard:cumulative_publications_stats")
    response = client.get(url)

    data = json.loads(response.content)
    assert response.status_code == 200
    assert len(data["data"]) == 0


# ============================================================================
# Tests for cumulative_impact_factor_stats
# ============================================================================


@pytest.mark.django_db
def test_cumulative_impact_factor_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:cumulative_impact_factor_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_cumulative_impact_factor_stats_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:cumulative_impact_factor_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_cumulative_impact_factor_stats_structure(
    client, staff_user, publications_with_impact_factor
):
    """Test weryfikujący strukturę danych dla impact factor."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:cumulative_impact_factor_stats")
    response = client.get(url)

    data = json.loads(response.content)
    assert "data" in data
    assert "layout" in data

    if len(data["data"]) > 0:
        chart_data = data["data"][0]
        assert chart_data["type"] == "scatter"
        assert chart_data["mode"] == "lines"


# ============================================================================
# Tests for cumulative_points_kbn_stats
# ============================================================================


@pytest.mark.django_db
def test_cumulative_points_kbn_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:cumulative_points_kbn_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_cumulative_points_kbn_stats_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:cumulative_points_kbn_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_cumulative_points_kbn_stats_structure(
    client, staff_user, publications_with_points
):
    """Test weryfikujący strukturę danych dla punktów MNiSW."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:cumulative_points_kbn_stats")
    response = client.get(url)

    data = json.loads(response.content)
    assert "data" in data
    assert "layout" in data

    if len(data["data"]) > 0:
        chart_data = data["data"][0]
        assert chart_data["type"] == "scatter"
        assert chart_data["mode"] == "lines"
