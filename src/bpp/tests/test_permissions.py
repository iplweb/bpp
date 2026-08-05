"""Testy centralnej bramki autoryzacji dla operacji redaktorskich
(`bpp.permissions`).

Kontrakt:
- `moze_wprowadzac_dane(user)` — superuser LUB członek grupy
  ``GR_WPROWADZANIE_DANYCH``; anonim / zwykły użytkownik → False.
- `WprowadzanieDanychRequiredMixin` i `wprowadzanie_danych_wymagane`:
  anonim → 302 (login), zalogowany-bez-uprawnień → 403 (PermissionDenied),
  uprawniony → normalna odpowiedź widoku.
"""

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.views import View
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.permissions import (
    WprowadzanieDanychRequiredMixin,
    moze_wprowadzac_dane,
    wprowadzanie_danych_wymagane,
    wymagaj_wprowadzania_danych_dla_urlpatterns,
)


@pytest.fixture
def wprowadzanie_danych_group(db):
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    return group


@pytest.fixture
def zwykly_user(db):
    """Zalogowany, ale bez żadnych uprawnień redaktorskich."""
    return baker.make("bpp.BppUser", is_staff=False, is_superuser=False)


@pytest.fixture
def user_z_grupa(db, wprowadzanie_danych_group):
    user = baker.make("bpp.BppUser", is_staff=True, is_superuser=False)
    user.groups.add(wprowadzanie_danych_group)
    return user


@pytest.fixture
def superuser(db):
    return baker.make("bpp.BppUser", is_staff=True, is_superuser=True)


# --- moze_wprowadzac_dane ------------------------------------------------


def test_moze_wprowadzac_dane_anonim_odmawia():
    assert moze_wprowadzac_dane(AnonymousUser()) is False


def test_moze_wprowadzac_dane_zwykly_user_odmawia(zwykly_user):
    assert moze_wprowadzac_dane(zwykly_user) is False


def test_moze_wprowadzac_dane_grupa_przepuszcza(user_z_grupa):
    assert moze_wprowadzac_dane(user_z_grupa) is True


def test_moze_wprowadzac_dane_superuser_przepuszcza(superuser):
    assert moze_wprowadzac_dane(superuser) is True


# --- dekorator FBV -------------------------------------------------------


def _widok_fbv(request):
    return HttpResponse("ok")


def test_dekorator_anonim_przekierowuje_na_login(rf):
    request = rf.get("/")
    request.user = AnonymousUser()
    response = wprowadzanie_danych_wymagane(_widok_fbv)(request)
    assert response.status_code == 302


def test_dekorator_zwykly_user_403(rf, zwykly_user):
    request = rf.get("/")
    request.user = zwykly_user
    with pytest.raises(PermissionDenied):
        wprowadzanie_danych_wymagane(_widok_fbv)(request)


def test_dekorator_grupa_przepuszcza(rf, user_z_grupa):
    request = rf.get("/")
    request.user = user_z_grupa
    response = wprowadzanie_danych_wymagane(_widok_fbv)(request)
    assert response.status_code == 200


def test_dekorator_superuser_przepuszcza(rf, superuser):
    request = rf.get("/")
    request.user = superuser
    response = wprowadzanie_danych_wymagane(_widok_fbv)(request)
    assert response.status_code == 200


# --- mixin CBV -----------------------------------------------------------


class _WidokCBV(WprowadzanieDanychRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("ok")


def test_mixin_anonim_przekierowuje_na_login(rf):
    request = rf.get("/")
    request.user = AnonymousUser()
    response = _WidokCBV.as_view()(request)
    assert response.status_code == 302


def test_mixin_zwykly_user_403(rf, zwykly_user):
    request = rf.get("/")
    request.user = zwykly_user
    with pytest.raises(PermissionDenied):
        _WidokCBV.as_view()(request)


def test_mixin_grupa_przepuszcza(rf, user_z_grupa):
    request = rf.get("/")
    request.user = user_z_grupa
    response = _WidokCBV.as_view()(request)
    assert response.status_code == 200


def test_mixin_superuser_przepuszcza(rf, superuser):
    request = rf.get("/")
    request.user = superuser
    response = _WidokCBV.as_view()(request)
    assert response.status_code == 200


# --- owijanie całego URLconf-a (bramkowanie aplikacji) -------------------


def test_wrapper_owija_kazdy_wzorzec(rf, zwykly_user, superuser):
    """`wymagaj_wprowadzania_danych_dla_urlpatterns` bramkuje każdy widok
    listy URL — zwykły user → 403, uprawniony → normalna odpowiedź."""
    from django.urls import path

    patterns = wymagaj_wprowadzania_danych_dla_urlpatterns(
        [path("x/", _widok_fbv, name="x")]
    )
    callback = patterns[0].callback

    request = rf.get("/x/")
    request.user = zwykly_user
    with pytest.raises(PermissionDenied):
        callback(request)

    request = rf.get("/x/")
    request.user = superuser
    assert callback(request).status_code == 200
