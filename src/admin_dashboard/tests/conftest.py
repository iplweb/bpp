"""
Fixtures for admin_dashboard tests.
"""

from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker

from bpp.models import (
    Patent,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

User = get_user_model()


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
def publications_with_charakter(db, charaktery_formalne):
    """Tworzy publikacje z różnymi charakterami formalnymi."""
    ac = charaktery_formalne["AC"]
    ksp = charaktery_formalne["KSP"]
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
        pub = baker.make(Patent)
        publications.append(pub)

    return publications


@pytest.fixture
def menu_clicks_for_user(db, staff_user):
    """Tworzy przykładowe kliknięcia w menu dla użytkownika."""
    from admin_dashboard.models import MenuClick

    clicks = []
    # BPP - 5 kliknięć
    for _ in range(5):
        click = baker.make(MenuClick, user=staff_user, menu_label="BPP", menu_url="/")
        clicks.append(click)

    # Panel - 3 kliknięcia
    for _ in range(3):
        click = baker.make(
            MenuClick, user=staff_user, menu_label="Panel", menu_url="/admin/"
        )
        clicks.append(click)

    # WWW - 2 kliknięcia
    for _ in range(2):
        click = baker.make(
            MenuClick, user=staff_user, menu_label="WWW", menu_url="/admin/web/"
        )
        clicks.append(click)

    return clicks
