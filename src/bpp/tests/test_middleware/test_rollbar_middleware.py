import pytest
from django.contrib.auth.models import AnonymousUser
from model_bakery import baker

from bpp.middleware import CustomRollbarNotifierMiddleware


@pytest.fixture
def middleware(settings):
    # Bez access_token RollbarNotifierMiddleware.__init__ rzuca
    # MiddlewareNotUsed; podajemy atrapę, by powołać obiekt w teście.
    settings.ROLLBAR = {"access_token": "test-token", "environment": "test"}
    return CustomRollbarNotifierMiddleware(get_response=lambda request: None)


@pytest.mark.django_db
def test_get_payload_data_zalogowany_login_w_custom(middleware, rf):
    """Zalogowany użytkownik: jego login trafia do pola `custom`."""
    user = baker.make("bpp.BppUser", username="jkowalski")
    request = rf.get("/")
    request.user = user

    payload = middleware.get_payload_data(request, None)

    assert payload["custom"]["login"] == "jkowalski"
    assert payload["custom"]["zalogowany"] is True
    # person nadal wypełnione dla dashboardu "users affected"
    assert payload["person"]["username"] == "jkowalski"


def test_get_payload_data_anonimowy_oznaczony_w_custom(middleware, rf):
    """Niezalogowany użytkownik: pole `custom` oznacza go jako anonimowego."""
    request = rf.get("/")
    request.user = AnonymousUser()

    payload = middleware.get_payload_data(request, None)

    assert payload["custom"]["zalogowany"] is False
    assert "anonim" in payload["custom"]["login"].lower()
    # brak sekcji person — anonim nie ma id
    assert "person" not in payload
