"""Regresja bezpieczeństwa: widoki optymalizacji publikacji
(przypinanie/odpinanie/zmiana dyscyplin) wymagają uprawnień redaktorskich.
Wcześniej używały ``LoginRequiredMixin`` (samo zalogowanie).
"""

import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.fixture
def zwykly_user(db):
    return baker.make("bpp.BppUser", is_staff=False, is_superuser=False)


@pytest.mark.django_db
def test_zwykly_user_dostaje_403(client, zwykly_user):
    client.force_login(zwykly_user)
    url = reverse("ewaluacja_optymalizuj_publikacje:index")
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_anonim_przekierowuje_na_login(client):
    url = reverse("ewaluacja_optymalizuj_publikacje:index")
    assert client.get(url).status_code == 302


@pytest.mark.django_db
def test_redaktor_ma_dostep(admin_client):
    """Kontrola pozytywna: redaktor (superuser) przechodzi bramkę."""
    url = reverse("ewaluacja_optymalizuj_publikacje:index")
    assert admin_client.get(url).status_code != 403
