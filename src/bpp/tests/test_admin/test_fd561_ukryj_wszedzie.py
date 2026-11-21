"""FD#561: akcje masowe „Ukryj/Pokaż wybranych autorów wszędzie”."""

from unittest import mock

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import transaction
from django.test import RequestFactory
from model_bakery import baker
from reversion.models import Version

from bpp.admin import actions
from bpp.admin.autor import AutorAdmin
from bpp.models import Autor

POLA = actions.POLA_WIDOCZNOSCI_AUTORA


def _request(user):
    request = RequestFactory().get("/admin/bpp/autor/")
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _admin():
    return AutorAdmin(Autor, AdminSite())


def _flagi(autor):
    autor.refresh_from_db()
    return {pole: getattr(autor, pole) for pole in POLA}


def test_pola_widocznosci_obejmuja_api_i_strone_autora():
    assert set(POLA) == {
        "pokazuj_na_stronie_jednostki",
        "pokazuj_w_rankingu",
        "pokazuj_w_wyszukiwaniu",
        "pokazuj_w_indeksie",
        "pokazuj_w_api",
        "pokazuj_strone_autora",
    }


@pytest.mark.django_db
def test_ukryj_wszedzie_wylacza_wszystkie_flagi(admin_user):
    autor = baker.make(Autor)
    inny = baker.make(Autor)

    actions.ukryj_autorow_wszedzie(
        _admin(), _request(admin_user), Autor.objects.filter(pk=autor.pk)
    )

    assert _flagi(autor) == dict.fromkeys(POLA, False)
    # Autor spoza zaznaczenia nietknięty.
    assert _flagi(inny) == dict.fromkeys(POLA, True)


@pytest.mark.django_db
def test_pokaz_wszedzie_wlacza_wszystkie_flagi(admin_user):
    # Stan dozwolony przez constraint: strona schowana, wyszukiwanie i indeks
    # wyłączone — „pokaż” musi je włączyć razem ze stroną autora.
    autor = baker.make(Autor, **dict.fromkeys(POLA, False))

    actions.pokaz_autorow_wszedzie(
        _admin(), _request(admin_user), Autor.objects.filter(pk=autor.pk)
    )

    assert _flagi(autor) == dict.fromkeys(POLA, True)


@pytest.mark.django_db
def test_ukryj_wszedzie_czesciowo_ukryty_i_niezmiennik_modelu(admin_user):
    """Autor z włączonym wyszukiwaniem — samo wyłączenie strony autora
    złamałoby constraint; akcja wyłącza wszystko naraz i model przechodzi
    ``clean()``."""
    autor = baker.make(
        Autor,
        pokazuj_na_stronie_jednostki=False,
        pokazuj_w_rankingu=False,
    )

    actions.ukryj_autorow_wszedzie(
        _admin(), _request(admin_user), Autor.objects.filter(pk=autor.pk)
    )

    autor.refresh_from_db()
    autor.clean()
    assert _flagi(autor) == dict.fromkeys(POLA, False)


@pytest.mark.django_db
@pytest.mark.parametrize("akcja", ["ukryj_autorow_wszedzie", "pokaz_autorow_wszedzie"])
def test_akcja_wszedzie_uniewaznia_cache_raz(
    akcja, admin_user, django_capture_on_commit_callbacks
):
    widoczny = akcja == "ukryj_autorow_wszedzie"
    autorzy = baker.make(Autor, _quantity=3, **dict.fromkeys(POLA, widoczny))

    transaction.get_connection().run_on_commit.clear()
    with (
        mock.patch("bpp.views.cache_publiczny._wykonaj_bump") as bump,
        django_capture_on_commit_callbacks(execute=True),
    ):
        getattr(actions, akcja)(
            _admin(),
            _request(admin_user),
            Autor.objects.filter(pk__in=[a.pk for a in autorzy]),
        )

    assert bump.call_count == 1


@pytest.mark.django_db
def test_ukryj_wszedzie_logentry_wersja_i_komunikat(admin_user):
    ukryty_juz = baker.make(Autor, **dict.fromkeys(POLA, False))
    autorzy = baker.make(Autor, _quantity=2)
    request = _request(admin_user)

    actions.ukryj_autorow_wszedzie(
        _admin(),
        request,
        Autor.objects.filter(pk__in=[ukryty_juz.pk] + [a.pk for a in autorzy]),
    )

    for autor in autorzy:
        wpis = LogEntry.objects.get(object_id=str(autor.pk))
        assert wpis.action_flag == CHANGE
        assert wpis.user == admin_user
        assert wpis.change_message == "Ukryto wszędzie (akcja masowa)"
        wersje = Version.objects.get_for_object(autor)
        # Stan sprzed zmiany + stan po zmianie — da się cofnąć z „Historii”.
        assert wersje.count() == 2
        assert wersje.first().field_dict["pokazuj_w_api"] is False
        assert wersje.last().field_dict["pokazuj_w_api"] is True

    # Autor, który już był ukryty wszędzie, nie dostaje wpisu.
    assert not LogEntry.objects.filter(object_id=str(ukryty_juz.pk)).exists()

    komunikaty = [str(m) for m in get_messages(request)]
    assert komunikaty == ["Ukryto wszędzie 2 autorów"]


@pytest.mark.django_db
def test_pokaz_wszedzie_bez_zmian_nic_nie_loguje(admin_user):
    autor = baker.make(Autor)
    request = _request(admin_user)

    actions.pokaz_autorow_wszedzie(_admin(), request, Autor.objects.filter(pk=autor.pk))

    assert not LogEntry.objects.exists()
    assert [str(m) for m in get_messages(request)] == ["Pokazano wszędzie 0 autorów"]


@pytest.mark.django_db
def test_akcje_wszedzie_wymagaja_uprawnienia_change(django_user_model):
    user = django_user_model.objects.create_user(
        "tylko_podglad", password="x", is_staff=True
    )
    user.user_permissions.add(Permission.objects.get(codename="view_autor"))
    user = django_user_model.objects.get(pk=user.pk)
    request = _request(user)
    request.user.cached_groups = []

    dostepne = _admin().get_actions(request)
    assert "ukryj_autorow_wszedzie" not in dostepne
    assert "pokaz_autorow_wszedzie" not in dostepne

    user.user_permissions.add(Permission.objects.get(codename="change_autor"))
    user = django_user_model.objects.get(pk=user.pk)
    request = _request(user)
    request.user.cached_groups = []

    dostepne = _admin().get_actions(request)
    assert "ukryj_autorow_wszedzie" in dostepne
    assert "pokaz_autorow_wszedzie" in dostepne
