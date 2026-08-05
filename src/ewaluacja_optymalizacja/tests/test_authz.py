"""Regresja bezpieczeństwa: CAŁA aplikacja ``ewaluacja_optymalizacja`` to
narzędzie redaktorskie — każdy widok wymaga uprawnień „wprowadzanie danych".

Bramka jest nałożona na poziomie URLconf
(``wymagaj_wprowadzania_danych_dla_urlpatterns``), więc test sprawdza
reprezentatywny zestaw tras (w tym mutujące: analiza odpinania, toggle-pin).
Wcześniej widoki miały tylko ``@login_required``.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

ROUTES = [
    ("ewaluacja_optymalizacja:index", {}),
    ("ewaluacja_optymalizacja:analyze-unpinning", {}),
    ("ewaluacja_optymalizacja:unpinning-list", {}),
    ("ewaluacja_optymalizacja:browser-toggle-pin", {"model_type": "ciagle", "pk": 1}),
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
    assert client.get(url).status_code == 302
