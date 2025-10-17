"""
Testy dla django_countdown - skupione na krytycznych funkcjonalnościach.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone
from model_bakery import baker

from django_countdown.context_processors import countdown_context
from django_countdown.middleware import CountdownBlockingMiddleware
from django_countdown.models import SiteCountdown

User = get_user_model()


def add_session_to_request(request):
    """Helper: dodaje sesję do requesta z RequestFactory."""
    request.session = SessionStore()
    request.session.save()


# ============================================================================
# MODEL TESTS - najważniejsze metody biznesowe
# ============================================================================


@pytest.mark.django_db
def test_sitecountdown_is_expired_when_time_passed():
    """Test czy is_expired() poprawnie wykrywa wygaśnięcie."""
    past_time = timezone.now() - timedelta(hours=1)
    countdown = baker.make(SiteCountdown, countdown_time=past_time)

    assert countdown.is_expired() is True


@pytest.mark.django_db
def test_sitecountdown_is_not_expired_when_time_future():
    """Test czy is_expired() zwraca False dla przyszłej daty."""
    future_time = timezone.now() + timedelta(hours=1)
    countdown = baker.make(SiteCountdown, countdown_time=future_time)

    assert countdown.is_expired() is False


@pytest.mark.django_db
def test_sitecountdown_is_expired_when_countdown_time_is_none():
    """Test edge case: brak countdown_time."""
    countdown = baker.make(SiteCountdown, countdown_time=None)

    assert countdown.is_expired() is False


@pytest.mark.django_db
def test_sitecountdown_is_maintenance_finished_when_time_passed():
    """Test czy is_maintenance_finished() wykrywa koniec konserwacji."""
    past_time = timezone.now() - timedelta(hours=1)
    countdown = baker.make(SiteCountdown, maintenance_until=past_time)

    assert countdown.is_maintenance_finished() is True


@pytest.mark.django_db
def test_sitecountdown_is_maintenance_finished_when_no_maintenance_time():
    """Test edge case: brak maintenance_until."""
    countdown = baker.make(SiteCountdown, maintenance_until=None)

    assert countdown.is_maintenance_finished() is False


@pytest.mark.django_db
def test_sitecountdown_validation_prevents_past_countdown_time():
    """KRYTYCZNY: Test czy walidacja blokuje ustawienie czasu w przeszłości."""
    site = baker.make(Site)
    past_time = timezone.now() - timedelta(hours=1)

    countdown = SiteCountdown(
        site=site,
        countdown_time=past_time,
        message="Test",
    )

    with pytest.raises(ValidationError) as exc_info:
        countdown.clean()

    assert "countdown_time" in exc_info.value.error_dict


@pytest.mark.django_db
def test_sitecountdown_validation_maintenance_must_be_after_countdown():
    """KRYTYCZNY: Test walidacji kolejności dat konserwacji."""
    site = baker.make(Site)
    countdown_time = timezone.now() + timedelta(hours=2)
    # Maintenance kończy się PRZED countdown_time - to błąd!
    maintenance_until = countdown_time - timedelta(hours=1)

    countdown = SiteCountdown(
        site=site,
        countdown_time=countdown_time,
        maintenance_until=maintenance_until,
        message="Test",
    )

    with pytest.raises(ValidationError) as exc_info:
        countdown.clean()

    assert "maintenance_until" in exc_info.value.error_dict


@pytest.mark.django_db
def test_sitecountdown_time_remaining_calculates_correctly():
    """Test kalkulacji pozostałego czasu."""
    future_time = timezone.now() + timedelta(hours=2, minutes=30)
    countdown = baker.make(SiteCountdown, countdown_time=future_time)

    result = countdown.time_remaining()

    # Sprawdź czy zawiera "godz" i "min" (bez dokładnej wartości bo czas płynie)
    assert "godz" in result or "min" in result
    assert result != "Wygasło"


@pytest.mark.django_db
def test_sitecountdown_time_remaining_when_expired():
    """Test zwracania 'Wygasło' dla przeszłej daty."""
    past_time = timezone.now() - timedelta(hours=1)
    countdown = baker.make(SiteCountdown, countdown_time=past_time)

    assert countdown.time_remaining() == "Wygasło"


# ============================================================================
# MIDDLEWARE TESTS - kluczowa logika blokowania
# ============================================================================


@pytest.mark.django_db
def test_middleware_blocks_access_when_countdown_expired(mocker):
    """KRYTYCZNY: Test czy middleware blokuje dostęp po wygaśnięciu."""
    site = Site.objects.get_current()
    past_time = timezone.now() - timedelta(hours=1)
    baker.make(SiteCountdown, site=site, countdown_time=past_time)

    factory = RequestFactory()
    request = factory.get("/")
    request.user = baker.make(User, is_superuser=False, username="testuser")
    add_session_to_request(request)

    # Mock render() żeby zwracał HttpResponse bez renderowania templateka
    mock_response = HttpResponse(status=503)
    mocker.patch("django_countdown.middleware.render", return_value=mock_response)

    middleware = CountdownBlockingMiddleware(lambda r: None)
    response = middleware.process_request(request)

    assert response is not None
    assert response.status_code == 503


@pytest.mark.django_db
def test_middleware_allows_access_when_countdown_not_expired():
    """Test czy middleware pozwala na dostęp gdy countdown nie wygasł."""
    site = Site.objects.get_current()
    future_time = timezone.now() + timedelta(hours=1)
    baker.make(SiteCountdown, site=site, countdown_time=future_time)

    factory = RequestFactory()
    request = factory.get("/")

    middleware = CountdownBlockingMiddleware(lambda r: None)
    response = middleware.process_request(request)

    assert response is None  # Brak blokady


@pytest.mark.django_db
def test_middleware_allows_superuser_when_countdown_expired():
    """KRYTYCZNY: Superuser MUSI mieć dostęp żeby wyłączyć countdown!"""
    site = Site.objects.get_current()
    past_time = timezone.now() - timedelta(hours=1)
    baker.make(SiteCountdown, site=site, countdown_time=past_time)

    factory = RequestFactory()
    request = factory.get("/")
    request.user = baker.make(User, is_superuser=True, username="admin")

    middleware = CountdownBlockingMiddleware(lambda r: None)
    response = middleware.process_request(request)

    assert response is None  # Superuser ma dostęp


@pytest.mark.django_db
def test_middleware_allows_access_after_maintenance_finished():
    """KRYTYCZNY: Po zakończeniu konserwacji dostęp powinien być otwarty."""
    site = Site.objects.get_current()
    countdown_time = timezone.now() - timedelta(hours=2)
    maintenance_until = timezone.now() - timedelta(hours=1)  # Już minęło

    baker.make(
        SiteCountdown,
        site=site,
        countdown_time=countdown_time,
        maintenance_until=maintenance_until,
    )

    factory = RequestFactory()
    request = factory.get("/")
    request.user = baker.make(User, is_superuser=False)

    middleware = CountdownBlockingMiddleware(lambda r: None)
    response = middleware.process_request(request)

    assert response is None  # Dostęp otwarty po konserwacji


@pytest.mark.django_db
def test_middleware_allows_admin_paths():
    """Test czy middleware nie blokuje ścieżek /admin/."""
    site = Site.objects.get_current()
    past_time = timezone.now() - timedelta(hours=1)
    baker.make(SiteCountdown, site=site, countdown_time=past_time)

    factory = RequestFactory()
    request = factory.get("/admin/")

    middleware = CountdownBlockingMiddleware(lambda r: None)
    response = middleware.process_request(request)

    assert response is None  # /admin/ zawsze dostępny


@pytest.mark.django_db
def test_middleware_allows_static_paths():
    """Test czy middleware nie blokuje /static/ i /media/."""
    site = Site.objects.get_current()
    past_time = timezone.now() - timedelta(hours=1)
    baker.make(SiteCountdown, site=site, countdown_time=past_time)

    factory = RequestFactory()
    middleware = CountdownBlockingMiddleware(lambda r: None)

    # Test /static/
    request_static = factory.get("/static/css/style.css")
    assert middleware.process_request(request_static) is None

    # Test /media/
    request_media = factory.get("/media/image.jpg")
    assert middleware.process_request(request_media) is None


@pytest.mark.django_db
def test_middleware_handles_no_countdown_gracefully():
    """Test edge case: brak countdown dla site."""
    factory = RequestFactory()
    request = factory.get("/")

    middleware = CountdownBlockingMiddleware(lambda r: None)
    response = middleware.process_request(request)

    assert response is None  # Normalny dostęp gdy brak countdown


# ============================================================================
# CONTEXT PROCESSOR TESTS - dostępność countdownu w template
# ============================================================================


@pytest.mark.django_db
def test_context_processor_returns_active_countdown_when_not_expired():
    """Test czy context processor zwraca aktywny countdown."""
    site = Site.objects.get_current()
    future_time = timezone.now() + timedelta(hours=1)
    countdown = baker.make(SiteCountdown, site=site, countdown_time=future_time)

    factory = RequestFactory()
    request = factory.get("/")

    context = countdown_context(request)

    assert context["active_countdown"] == countdown
    assert context["maintenance_countdown"] is None


@pytest.mark.django_db
def test_context_processor_returns_none_when_countdown_expired():
    """Test czy context processor nie zwraca wygasłego countdownu."""
    site = Site.objects.get_current()
    past_time = timezone.now() - timedelta(hours=1)
    baker.make(SiteCountdown, site=site, countdown_time=past_time)

    factory = RequestFactory()
    request = factory.get("/")
    request.user = baker.make(User, is_superuser=False)

    context = countdown_context(request)

    assert context["active_countdown"] is None


@pytest.mark.django_db
def test_context_processor_shows_maintenance_countdown_to_superuser():
    """Test czy superuser widzi countdown w trakcie konserwacji."""
    site = Site.objects.get_current()
    countdown_time = timezone.now() - timedelta(hours=1)
    maintenance_until = timezone.now() + timedelta(hours=1)  # Jeszcze trwa

    countdown = baker.make(
        SiteCountdown,
        site=site,
        countdown_time=countdown_time,
        maintenance_until=maintenance_until,
    )

    factory = RequestFactory()
    request = factory.get("/")
    request.user = baker.make(User, is_superuser=True, username="admin")

    context = countdown_context(request)

    assert context["active_countdown"] is None
    assert context["maintenance_countdown"] == countdown


@pytest.mark.django_db
def test_context_processor_handles_no_countdown():
    """Test edge case: brak countdown."""
    factory = RequestFactory()
    request = factory.get("/")

    context = countdown_context(request)

    assert context["active_countdown"] is None
    assert context["maintenance_countdown"] is None
