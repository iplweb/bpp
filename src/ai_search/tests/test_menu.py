import pytest
from django.urls import reverse


@pytest.fixture
def staff_client(client, django_user_model):
    u = django_user_model.objects.create_user(
        username="ed", password="x", is_staff=True, is_superuser=True
    )
    client.force_login(u)
    return client


@pytest.mark.django_db
def test_menu_item_shown_when_enabled(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    r = staff_client.get("/")
    assert reverse("ai_search:index") in r.content.decode()


@pytest.mark.django_db
def test_menu_item_hidden_when_disabled(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = False
    r = staff_client.get("/")
    assert reverse("ai_search:index") not in r.content.decode()
