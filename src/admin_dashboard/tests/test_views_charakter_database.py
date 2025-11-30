"""
Tests for charakter formalny stats, database stats, helper functions, and menu clicks in admin_dashboard.
"""

import json

import pytest
from django.urls import reverse

from admin_dashboard.views import (
    _get_admin_url_for_charakter,
    _get_charakter_counts,
)
from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

# ============================================================================
# Tests for charakter_formalny_stats
# ============================================================================


@pytest.mark.django_db
def test_charakter_formalny_stats_top90_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:charakter_formalny_stats_top90")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_charakter_formalny_stats_top90_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:charakter_formalny_stats_top90")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_charakter_formalny_stats_top90_structure(
    client, staff_user, publications_with_charakter
):
    """Test weryfikujący strukturę danych dla top 90% charakterów."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:charakter_formalny_stats_top90")
    response = client.get(url)

    data = json.loads(response.content)
    assert "data" in data
    assert "layout" in data

    chart_data = data["data"][0]
    assert chart_data["type"] == "pie"
    assert chart_data["hole"] == 0.4  # Donut chart
    assert "labels" in chart_data
    assert "values" in chart_data
    assert "customdata" in chart_data


@pytest.mark.django_db
def test_charakter_formalny_stats_remaining10_returns_json(client, staff_user):
    """Test weryfikujący, że widok remaining10 zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:charakter_formalny_stats_remaining10")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_charakter_formalny_stats_remaining1_returns_json(client, staff_user):
    """Test weryfikujący, że widok remaining1 zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:charakter_formalny_stats_remaining1")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


# ============================================================================
# Tests for database_stats
# ============================================================================


@pytest.mark.django_db
def test_database_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:database_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_database_stats_returns_json(client, staff_user):
    """Test weryfikujący, że widok zwraca JSON."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:database_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_database_stats_structure(client, staff_user, publications_with_years):
    """Test weryfikujący strukturę danych database_stats."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:database_stats")
    response = client.get(url)

    data = json.loads(response.content)
    assert "type_distribution" in data
    assert "trend_data" in data
    assert "trend_layout" in data


# ============================================================================
# Tests for helper functions
# ============================================================================


@pytest.mark.django_db
def test_get_admin_url_for_charakter_patent():
    """Test weryfikujący URL dla patentu."""
    url = _get_admin_url_for_charakter("PAT", 1, 10, 5)
    assert "/admin/bpp/patent/" in url
    assert "charakter_formalny__id__exact=1" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_praca_doktorska():
    """Test weryfikujący URL dla pracy doktorskiej."""
    url = _get_admin_url_for_charakter("D", 2, 10, 5)
    assert "/admin/bpp/praca_doktorska/" in url
    assert "charakter_formalny__id__exact=2" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_praca_habilitacyjna():
    """Test weryfikujący URL dla pracy habilitacyjnej."""
    url = _get_admin_url_for_charakter("H", 3, 10, 5)
    assert "/admin/bpp/praca_habilitacyjna/" in url
    assert "charakter_formalny__id__exact=3" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_ciagle_more():
    """Test weryfikujący URL dla wydawnictw ciągłych (gdy więcej niż zwartych)."""
    url = _get_admin_url_for_charakter("AC", 4, 100, 50)
    assert "/admin/bpp/wydawnictwo_ciagle/" in url
    assert "charakter_formalny__id__exact=4" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_zwarte_more():
    """Test weryfikujący URL dla wydawnictw zwartych (gdy więcej niż ciągłych)."""
    url = _get_admin_url_for_charakter("KSP", 5, 30, 70)
    assert "/admin/bpp/wydawnictwo_zwarte/" in url
    assert "charakter_formalny__id__exact=5" in url


@pytest.mark.django_db
def test_get_charakter_counts_empty_database():
    """Test weryfikujący _get_charakter_counts dla pustej bazy."""
    Wydawnictwo_Ciagle.objects.all().delete()
    Wydawnictwo_Zwarte.objects.all().delete()

    result = _get_charakter_counts()
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.django_db
def test_get_charakter_counts_with_data(publications_with_charakter):
    """Test weryfikujący _get_charakter_counts z danymi."""
    result = _get_charakter_counts()

    assert isinstance(result, list)
    assert len(result) > 0

    # Każdy element to tuple: (nazwa, count, skrot, id, ciagle_count, zwarte_count)
    for char in result:
        assert len(char) == 6
        nazwa, count, skrot, char_id, ciagle, zwarte = char
        assert isinstance(nazwa, str)
        assert isinstance(count, int)
        assert isinstance(skrot, str)
        assert count == ciagle + zwarte

    # Sprawdź, że lista jest posortowana malejąco według count
    counts = [char[1] for char in result]
    assert counts == sorted(counts, reverse=True)


# ============================================================================
# Tests for menu clicks tracking
# ============================================================================


@pytest.mark.django_db
def test_log_menu_click_requires_staff(client, regular_user):
    """Test weryfikujący, że endpoint wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:log_menu_click")
    response = client.post(url, {"menu_label": "BPP", "menu_url": "/"})
    assert response.status_code == 302  # Redirect do logowania


@pytest.mark.django_db
def test_log_menu_click_authenticated_success(client, staff_user):
    """Test weryfikujący, że zalogowany staff może zapisać kliknięcie."""
    from admin_dashboard.models import MenuClick

    client.force_login(staff_user)
    url = reverse("admin_dashboard:log_menu_click")

    initial_count = MenuClick.objects.filter(user=staff_user).count()

    response = client.post(url, {"menu_label": "BPP", "menu_url": "/"})

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "ok"

    # Sprawdź, że kliknięcie zostało zapisane
    assert MenuClick.objects.filter(user=staff_user).count() == initial_count + 1

    # Sprawdź poprawność danych
    click = MenuClick.objects.filter(user=staff_user).latest("clicked_at")
    assert click.menu_label == "BPP"
    assert click.menu_url == "/"


@pytest.mark.django_db
def test_log_menu_click_requires_post(client, staff_user):
    """Test weryfikujący, że endpoint wymaga metody POST."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:log_menu_click")
    response = client.get(url)
    assert response.status_code == 405  # Method not allowed


@pytest.mark.django_db
def test_log_menu_click_requires_menu_label(client, staff_user):
    """Test weryfikujący, że endpoint wymaga menu_label."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:log_menu_click")
    response = client.post(url, {"menu_url": "/"})
    assert response.status_code == 400
    data = json.loads(response.content)
    assert "error" in data


@pytest.mark.django_db
def test_log_menu_click_requires_menu_url(client, staff_user):
    """Test weryfikujący, że endpoint wymaga menu_url."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:log_menu_click")
    response = client.post(url, {"menu_label": "BPP"})
    assert response.status_code == 400
    data = json.loads(response.content)
    assert "error" in data


@pytest.mark.django_db
def test_log_menu_click_max_1000_per_user(client, staff_user):
    """Test weryfikujący, że użytkownik ma maksymalnie 1000 wpisów."""
    from admin_dashboard.models import MenuClick

    client.force_login(staff_user)

    # Utwórz 1001 kliknięć (signal powinien usunąć najstarsze)
    for i in range(1001):
        MenuClick.objects.create(
            user=staff_user, menu_label=f"Menu{i}", menu_url=f"/url{i}/"
        )

    # Sprawdź, że jest dokładnie 1000 wpisów
    count = MenuClick.objects.filter(user=staff_user).count()
    assert count == 1000


@pytest.mark.django_db
def test_menu_clicks_stats_requires_staff(client, regular_user):
    """Test weryfikujący, że widok wymaga uprawnień staff."""
    client.force_login(regular_user)
    url = reverse("admin_dashboard:menu_clicks_stats")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_menu_clicks_stats_returns_top_10(client, staff_user, menu_clicks_for_user):
    """Test weryfikujący, że widok zwraca top 10 pozycji."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:menu_clicks_stats")
    response = client.get(url)

    assert response.status_code == 200
    assert "top_clicks" in response.context

    top_clicks = response.context["top_clicks"]
    assert len(top_clicks) <= 10

    # Sprawdź sortowanie według count (malejąco)
    counts = [click["count"] for click in top_clicks]
    assert counts == sorted(counts, reverse=True)

    # Sprawdź pierwsze 3 pozycje
    assert top_clicks[0]["menu_label"] == "BPP"
    assert top_clicks[0]["count"] == 5
    assert top_clicks[1]["menu_label"] == "Panel"
    assert top_clicks[1]["count"] == 3
    assert top_clicks[2]["menu_label"] == "WWW"
    assert top_clicks[2]["count"] == 2


@pytest.mark.django_db
def test_menu_clicks_stats_per_user(client, staff_user, superuser):
    """Test weryfikujący, że statystyki są per użytkownik."""
    from admin_dashboard.models import MenuClick

    # Kliknięcia staff_user
    for _ in range(5):
        MenuClick.objects.create(user=staff_user, menu_label="BPP", menu_url="/")

    # Kliknięcia superuser
    for _ in range(10):
        MenuClick.objects.create(user=superuser, menu_label="Admin", menu_url="/admin/")

    # Sprawdź staff_user
    client.force_login(staff_user)
    url = reverse("admin_dashboard:menu_clicks_stats")
    response = client.get(url)

    top_clicks = response.context["top_clicks"]
    assert len(top_clicks) == 1
    assert top_clicks[0]["menu_label"] == "BPP"
    assert top_clicks[0]["count"] == 5

    # Sprawdź superuser
    client.force_login(superuser)
    response = client.get(url)

    top_clicks = response.context["top_clicks"]
    assert len(top_clicks) == 1
    assert top_clicks[0]["menu_label"] == "Admin"
    assert top_clicks[0]["count"] == 10


@pytest.mark.django_db
def test_menu_clicks_stats_empty_for_new_user(client, staff_user):
    """Test weryfikujący, że nowy użytkownik ma puste statystyki."""
    client.force_login(staff_user)
    url = reverse("admin_dashboard:menu_clicks_stats")
    response = client.get(url)

    assert response.status_code == 200
    top_clicks = response.context["top_clicks"]
    assert len(top_clicks) == 0
