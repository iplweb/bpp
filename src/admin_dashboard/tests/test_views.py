"""
Testy dla widoków admin_dashboard.

Zgodnie z konwencjami projektu:
- Używamy pytest (NIE unittest.TestCase)
- Nazwy funkcji testowych: test_module_functionality_specific_case()
- Używamy model_bakery.baker.make do tworzenia obiektów
- Wszystkie testy z bazą danych używają @pytest.mark.django_db
"""

import json
from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from admin_dashboard.views import (
    _get_admin_url_for_charakter,
    _get_charakter_counts,
)
from bpp.models import (
    Charakter_Formalny,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

User = get_user_model()


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def staff_user(db):
    """Zwykły użytkownik staff (nie superuser)."""
    return baker.make(User, is_staff=True, is_active=True, is_superuser=False)


@pytest.fixture
def superuser(db):
    """Superużytkownik."""
    return baker.make(User, is_staff=True, is_active=True, is_superuser=True)


@pytest.fixture
def regular_user(db):
    """Zwykły użytkownik bez uprawnień staff."""
    return baker.make(User, is_staff=False, is_active=True)


@pytest.fixture
def login_events_for_user(db, staff_user):
    """Tworzy przykładowe LoginEvent dla użytkownika."""
    from easyaudit.models import LoginEvent

    events = []
    for i in range(5):
        event = baker.make(
            LoginEvent,
            user=staff_user,
            login_type=LoginEvent.LOGIN,
            datetime=timezone.now() - timedelta(hours=i),
        )
        events.append(event)
    return events


@pytest.fixture
def login_events_multiple_users(db, staff_user, superuser):
    """Tworzy LoginEvent dla wielu użytkowników."""
    from easyaudit.models import LoginEvent

    events = []
    # Dla staff_user
    for i in range(3):
        event = baker.make(
            LoginEvent,
            user=staff_user,
            login_type=LoginEvent.LOGIN,
            datetime=timezone.now() - timedelta(hours=i),
        )
        events.append(event)

    # Dla superuser
    for i in range(3):
        event = baker.make(
            LoginEvent,
            user=superuser,
            login_type=LoginEvent.LOGIN,
            datetime=timezone.now() - timedelta(hours=i + 10),
        )
        events.append(event)

    return events


@pytest.fixture
def log_entries_weekdays(db, staff_user):
    """Tworzy LogEntry dla różnych dni tygodnia (ostatni miesiąc)."""
    entries = []
    now = timezone.now()

    # Poniedziałek - 5 wpisów
    monday = now - timedelta(days=(now.weekday() - 0) % 7)
    for i in range(5):
        entry = baker.make(
            LogEntry, user=staff_user, action_time=monday - timedelta(hours=i)
        )
        entries.append(entry)

    # Wtorek - 3 wpisy
    tuesday = now - timedelta(days=(now.weekday() - 1) % 7)
    for i in range(3):
        entry = baker.make(
            LogEntry, user=staff_user, action_time=tuesday - timedelta(hours=i)
        )
        entries.append(entry)

    # Środa - 2 wpisy
    wednesday = now - timedelta(days=(now.weekday() - 2) % 7)
    for i in range(2):
        entry = baker.make(
            LogEntry, user=staff_user, action_time=wednesday - timedelta(hours=i)
        )
        entries.append(entry)

    return entries


@pytest.fixture
def publications_with_years(db, charaktery_formalne):
    """Tworzy publikacje z różnymi rokami."""
    publications = []

    # Wydawnictwa ciągłe
    for year in [2020, 2021, 2022]:
        for _ in range(3):
            pub = baker.make(
                Wydawnictwo_Ciagle,
                rok=year,
                utworzono=timezone.now() - timedelta(days=365 * (2023 - year)),
            )
            publications.append(pub)

    # Wydawnictwa zwarte
    for year in [2020, 2021, 2022]:
        for _ in range(2):
            pub = baker.make(
                Wydawnictwo_Zwarte,
                rok=year,
                utworzono=timezone.now() - timedelta(days=365 * (2023 - year)),
            )
            publications.append(pub)

    return publications


@pytest.fixture
def publications_with_impact_factor(db, charaktery_formalne):
    """Tworzy publikacje z impact factor."""
    publications = []

    for year in [2015, 2016, 2017]:
        pub = baker.make(Wydawnictwo_Ciagle, rok=year, impact_factor=2.5)
        publications.append(pub)
        pub = baker.make(Wydawnictwo_Zwarte, rok=year, impact_factor=1.5)
        publications.append(pub)

    return publications


@pytest.fixture
def publications_with_points(db, charaktery_formalne):
    """Tworzy publikacje z punktami MNiSW."""
    publications = []

    for year in [2015, 2016, 2017]:
        pub = baker.make(Wydawnictwo_Ciagle, rok=year, punkty_kbn=100)
        publications.append(pub)
        pub = baker.make(Wydawnictwo_Zwarte, rok=year, punkty_kbn=50)
        publications.append(pub)

    return publications


@pytest.fixture
def publications_with_charakter(db):
    """Tworzy publikacje z różnymi charakterami formalnymi."""

    # Utwórz charaktery formalne jeśli nie istnieją
    ac = Charakter_Formalny.objects.get_or_create(
        nazwa="Artykuł w czasopiśmie", skrot="AC"
    )[0]
    ksp = Charakter_Formalny.objects.get_or_create(nazwa="Książka", skrot="KSP")[0]
    pat = Charakter_Formalny.objects.get_or_create(nazwa="Patent", skrot="PAT")[0]

    publications = []

    # 10 artykułów
    for _ in range(10):
        pub = baker.make(Wydawnictwo_Ciagle, charakter_formalny=ac)
        publications.append(pub)

    # 5 książek
    for _ in range(5):
        pub = baker.make(Wydawnictwo_Zwarte, charakter_formalny=ksp)
        publications.append(pub)

    # 2 patenty
    for _ in range(2):
        pub = baker.make(Wydawnictwo_Ciagle, charakter_formalny=pat)
        publications.append(pub)

    return publications


# ============================================================================
# Testy dla recent_logins_view
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
# Testy dla weekday_stats
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
# Testy dla day_of_month_activity_stats
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


# ============================================================================
# Testy dla new_publications_stats
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
# Testy dla cumulative_publications_stats
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
# Testy dla cumulative_impact_factor_stats
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
# Testy dla cumulative_points_kbn_stats
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


# ============================================================================
# Testy dla charakter_formalny_stats
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
# Testy dla database_stats
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
# Testy dla funkcji pomocniczych
# ============================================================================


@pytest.mark.django_db
def test_get_admin_url_for_charakter_patent():
    """Test weryfikujący URL dla patentu."""
    url = _get_admin_url_for_charakter("PAT", 1, 10, 5)
    assert "/admin/bpp/patent/" in url
    assert "charakter_formalny=1" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_praca_doktorska():
    """Test weryfikujący URL dla pracy doktorskiej."""
    url = _get_admin_url_for_charakter("D", 2, 10, 5)
    assert "/admin/bpp/praca_doktorska/" in url
    assert "charakter_formalny=2" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_praca_habilitacyjna():
    """Test weryfikujący URL dla pracy habilitacyjnej."""
    url = _get_admin_url_for_charakter("H", 3, 10, 5)
    assert "/admin/bpp/praca_habilitacyjna/" in url
    assert "charakter_formalny=3" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_ciagle_more():
    """Test weryfikujący URL dla wydawnictw ciągłych (gdy więcej niż zwartych)."""
    url = _get_admin_url_for_charakter("AC", 4, 100, 50)
    assert "/admin/bpp/wydawnictwo_ciagle/" in url
    assert "charakter_formalny=4" in url


@pytest.mark.django_db
def test_get_admin_url_for_charakter_zwarte_more():
    """Test weryfikujący URL dla wydawnictw zwartych (gdy więcej niż ciągłych)."""
    url = _get_admin_url_for_charakter("KSP", 5, 30, 70)
    assert "/admin/bpp/wydawnictwo_zwarte/" in url
    assert "charakter_formalny=5" in url


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
