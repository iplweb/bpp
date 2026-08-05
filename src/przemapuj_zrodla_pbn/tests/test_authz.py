"""Regresja bezpieczeństwa: widoki przemapowania/usuwania źródeł mutują dane
globalne, więc wymagają uprawnień redaktorskich (grupa „wprowadzanie danych"
lub superuser). Zwykłe zalogowane konto NIE może ich wywołać.

Wcześniej trasy były chronione tylko ``@login_required`` — zwykły użytkownik
skutecznie usuwał źródło (patrz historia ``test_views_actions.py``).
"""

import pytest
from django.urls import reverse
from model_bakery import baker

ROUTES = [
    ("przemapuj_zrodla_pbn:lista_skasowanych_zrodel", {}),
    ("przemapuj_zrodla_pbn:przemapuj_zrodlo", {"zrodlo_id": 1}),
    ("przemapuj_zrodla_pbn:usun_zrodlo", {"zrodlo_id": 1}),
]


@pytest.fixture
def zwykly_user(db):
    return baker.make("bpp.BppUser", is_staff=False, is_superuser=False)


@pytest.mark.django_db
@pytest.mark.parametrize("name,kwargs", ROUTES)
def test_zwykly_user_dostaje_403(client, zwykly_user, name, kwargs):
    client.force_login(zwykly_user)
    url = reverse(name, kwargs=kwargs)
    assert client.get(url).status_code == 403
    assert client.post(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("name,kwargs", ROUTES)
def test_anonim_przekierowuje_na_login(client, name, kwargs):
    url = reverse(name, kwargs=kwargs)
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_redaktor_ma_dostep(client, redaktor):
    """Kontrola pozytywna: redaktor przechodzi bramkę (widok listy → 200)."""
    url = reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")
    client.force_login(redaktor)
    assert client.get(url).status_code == 200
