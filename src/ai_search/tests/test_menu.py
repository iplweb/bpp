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
def test_menu_item_shown_when_configured(staff_client, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "anthropic"
    settings.BPP_AI_API_KEY = "sk-ant-test"
    r = staff_client.get("/")
    body = r.content.decode()
    assert reverse("ai_search:index") in body
    # pełny tryb — bez dopisku konfiguracyjnego
    assert "(konfiguracja)" not in body


@pytest.mark.django_db
def test_menu_item_shown_with_hint_when_not_configured(staff_client, settings):
    # Zmiana zachowania: gdy AI nie jest skonfigurowane, pozycja NADAL jest
    # widoczna dla personelu (prowadzi do instrukcji), ale z dopiskiem.
    settings.BPP_AI_SEARCH_ENABLED = False
    r = staff_client.get("/")
    body = r.content.decode()
    assert reverse("ai_search:index") in body
    assert "(konfiguracja)" in body


@pytest.mark.django_db
def test_menu_item_hidden_for_non_editor(client, django_user_model, settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_API_KEY = "sk-ant-test"
    u = django_user_model.objects.create_user(username="zwykly", password="x")
    client.force_login(u)
    r = client.get("/")
    assert reverse("ai_search:index") not in r.content.decode()
