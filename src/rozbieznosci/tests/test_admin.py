"""Uprawnienia admina dla modeli aplikacji ``rozbieznosci``.

Kasowanie publikacji pociąga za sobą (CASCADE) skasowanie powiązanych
z nią logów rozbieżności oraz wpisów o ignorowanych rozbieżnościach.
Django admin sprawdza uprawnienie do usunięcia KAŻDEGO obiektu kasowanego
kaskadowo -- patrz ``django.contrib.admin.utils.get_deleted_objects`` --
więc brak uprawnienia do modelu podrzędnego blokuje skasowanie publikacji.
"""

import pytest
from django.contrib.admin import site
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Wydawnictwo_Ciagle
from bpp.system import odtworz_grupy
from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


@pytest.mark.django_db
def test_admin_kasuje_publikacje_z_logiem_rozbieznosci(
    admin_client, wydawnictwo_ciagle
):
    """Superuser kasuje publikację, do której dopisano log zmiany punktacji."""
    baker.make(RozbieznoscLog, rekord=wydawnictwo_ciagle, metryka="if")
    pk = wydawnictwo_ciagle.pk

    res = admin_client.post(
        reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[pk]),
        {"post": "yes"},
    )

    assert res.status_code == 302
    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert not RozbieznoscLog.objects.filter(rekord_id=pk).exists()


@pytest.mark.django_db
def test_grupa_wprowadzanie_danych_kasuje_publikacje_z_rozbieznosciami(
    client, django_user_model, wydawnictwo_ciagle
):
    """Redaktor z grupy „wprowadzanie danych" też skasuje taką publikację."""
    odtworz_grupy()

    # Bez hasła — logujemy przez ``force_login``, które go nie sprawdza.
    user = django_user_model.objects.create_user(username="redaktor", is_staff=True)
    user.groups.add(Group.objects.get(name=GR_WPROWADZANIE_DANYCH))
    client.force_login(user)

    baker.make(RozbieznoscLog, rekord=wydawnictwo_ciagle, metryka="if")
    baker.make(IgnorowanaRozbieznosc, rekord=wydawnictwo_ciagle, metryka="mnisw")
    pk = wydawnictwo_ciagle.pk

    res = client.post(
        reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[pk]),
        {"post": "yes"},
    )

    assert res.status_code == 302
    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()


@pytest.fixture
def redaktor_client(client, django_user_model):
    """Zalogowany redaktor: staff + grupa „wprowadzanie danych"."""
    odtworz_grupy()
    # Bez hasła — logujemy przez ``force_login``, które go nie sprawdza.
    user = django_user_model.objects.create_user(username="redaktor", is_staff=True)
    user.groups.add(Group.objects.get(name=GR_WPROWADZANIE_DANYCH))
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,pole_dodatkowe",
    [
        (RozbieznoscLog, {"metryka": "if"}),
        (IgnorowanaRozbieznosc, {"metryka": "mnisw"}),
    ],
)
def test_redaktor_kasuje_wpis_wprost_z_listy(
    redaktor_client, wydawnictwo_ciagle, model, pole_dodatkowe
):
    """Logi to dane wtórne — redaktor kasuje je też bez kasowania publikacji."""
    obj = baker.make(model, rekord=wydawnictwo_ciagle, **pole_dodatkowe)
    opts = model._meta

    res = redaktor_client.post(
        reverse(f"admin:{opts.app_label}_{opts.model_name}_delete", args=[obj.pk]),
        {"post": "yes"},
    )

    assert res.status_code == 302
    assert not model.objects.filter(pk=obj.pk).exists()
    # Publikacja-rodzic ma to przeżyć: kasujemy dane wtórne, nie rekord.
    assert Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).exists()


@pytest.mark.django_db
def test_redaktor_nie_moze_dopisac_ani_zmienic_logu(redaktor_client):
    """Log pozostaje niepodrabialny: kasowalny, ale nie do dopisania/edycji."""
    admin_logu = site.get_model_admin(RozbieznoscLog)
    request = redaktor_client.request(PATH_INFO="/").wsgi_request

    assert admin_logu.has_delete_permission(request) is True
    assert admin_logu.has_add_permission(request) is False
    assert admin_logu.has_change_permission(request) is False
