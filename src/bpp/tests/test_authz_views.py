"""Regresja bezpieczeństwa dla widoków w aplikacji ``bpp``:

- ``toz`` (klonowanie rekordów) — mutacja tylko przez POST + CSRF, dostęp tylko
  dla redaktorów; GET już nie mutuje (405),
- widoki API punktacji/habilitacji/jednostki — dostęp tylko dla redaktorów.

Wcześniej trasy były chronione tylko zalogowaniem (``login_required`` /
``LoginRequiredMixin``), co pozwalało zwykłemu koncie m.in. nadpisywać
punktację źródeł i klonować rekordy.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle


@pytest.fixture
def zwykly_user(db):
    return baker.make("bpp.BppUser", is_staff=False, is_superuser=False)


# --- toz (klonowanie) ----------------------------------------------------

TOZ_URL = "admin_bpp_wydawnictwo_ciagle_toz"


@pytest.mark.django_db
def test_toz_post_klonuje_dla_redaktora(admin_client):
    """Kontrola pozytywna: POST redaktora klonuje rekord (UX bez zmian)."""
    c1 = baker.make(Wydawnictwo_Ciagle)
    url = reverse(TOZ_URL, args=[c1.pk])
    response = admin_client.post(url)
    assert response.status_code == 302
    assert Wydawnictwo_Ciagle.objects.count() == 2


@pytest.mark.django_db
def test_toz_get_nie_mutuje_405(admin_client):
    """GET już NIE klonuje (dawniej mutacja na GET) — 405, zero kopii."""
    c1 = baker.make(Wydawnictwo_Ciagle)
    url = reverse(TOZ_URL, args=[c1.pk])
    response = admin_client.get(url)
    assert response.status_code == 405
    assert Wydawnictwo_Ciagle.objects.count() == 1


@pytest.mark.django_db
def test_toz_zwykly_user_403(client, zwykly_user):
    c1 = baker.make(Wydawnictwo_Ciagle)
    url = reverse(TOZ_URL, args=[c1.pk])
    client.force_login(zwykly_user)
    assert client.post(url).status_code == 403
    assert Wydawnictwo_Ciagle.objects.count() == 1


@pytest.mark.django_db
def test_toz_anonim_przekierowuje(client):
    c1 = baker.make(Wydawnictwo_Ciagle)
    url = reverse(TOZ_URL, args=[c1.pk])
    assert client.post(url).status_code == 302


# --- API punktacji / habilitacji / jednostki -----------------------------

API_ROUTES = [
    ("bpp:api_rok_habilitacji", {}),
    ("bpp:api_punktacja_zrodla", {"zrodlo_id": 1, "rok": 2020}),
    ("bpp:api_upload_punktacja_zrodla", {"zrodlo_id": 1, "rok": 2020}),
    ("bpp:api_ostatnia_jednostka_i_dyscyplina", {}),
]


@pytest.mark.django_db
@pytest.mark.parametrize("name,kwargs", API_ROUTES)
def test_api_zwykly_user_403(client, zwykly_user, name, kwargs):
    client.force_login(zwykly_user)
    url = reverse(name, kwargs=kwargs)
    assert client.post(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("name,kwargs", API_ROUTES)
def test_api_anonim_przekierowuje(client, name, kwargs):
    url = reverse(name, kwargs=kwargs)
    assert client.post(url).status_code == 302
