"""Kasowanie autora, dla którego policzono udziały ewaluacyjne.

``IloscUdzialowDlaAutoraZa{Rok,Calosc}`` mają FK do ``Autor`` z ``CASCADE``,
a ich adminy dziedziczą po ``ReadonlyAdminMixin``, który odmawia kasowania
bezwarunkowo. Django pyta tą samą metodą o uprawnienia do obiektów kasowanych
kaskadowo (``django.contrib.admin.utils.get_deleted_objects``), więc taka
odmowa blokuje skasowanie samego autora -- również superuserowi.
"""

from decimal import Decimal

import pytest
from django.contrib.admin import site
from django.contrib.auth.models import Group
from django.urls import reverse

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.system import odtworz_grupy
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    IloscUdzialowDlaAutoraZaRok,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model", [IloscUdzialowDlaAutoraZaRok, IloscUdzialowDlaAutoraZaCalosc]
)
def test_admin_kasuje_autora_z_policzonymi_udzialami(
    admin_client, autor, dyscyplina1, model
):
    # ``LiczbaNField`` nie jest znany bakerowi — wartości podajemy wprost.
    model.objects.create(
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("1.0"),
        ilosc_udzialow_monografie=Decimal("0.5"),
        **({"rok": 2022} if model is IloscUdzialowDlaAutoraZaRok else {}),
    )
    pk = autor.pk

    res = admin_client.post(
        reverse("admin:bpp_autor_delete", args=[pk]), {"post": "yes"}
    )

    assert res.status_code == 302
    assert not Autor.objects.filter(pk=pk).exists()
    assert not model.objects.filter(autor_id=pk).exists()


@pytest.mark.django_db
def test_redaktor_kasuje_autora_z_policzonymi_udzialami(
    client, django_user_model, autor, dyscyplina1
):
    """Redaktor z grupy „wprowadzanie danych" też skasuje takiego autora."""
    odtworz_grupy()
    user = django_user_model.objects.create_user(username="redaktor", is_staff=True)
    user.groups.add(Group.objects.get(name=GR_WPROWADZANIE_DANYCH))
    client.force_login(user)

    for model in (IloscUdzialowDlaAutoraZaRok, IloscUdzialowDlaAutoraZaCalosc):
        model.objects.create(
            autor=autor,
            dyscyplina_naukowa=dyscyplina1,
            ilosc_udzialow=Decimal("1.0"),
            ilosc_udzialow_monografie=Decimal("0.5"),
            **({"rok": 2022} if model is IloscUdzialowDlaAutoraZaRok else {}),
        )
    pk = autor.pk

    res = client.post(reverse("admin:bpp_autor_delete", args=[pk]), {"post": "yes"})

    assert res.status_code == 302
    assert not Autor.objects.filter(pk=pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model", [IloscUdzialowDlaAutoraZaRok, IloscUdzialowDlaAutoraZaCalosc]
)
def test_udzialy_pozostaja_niedopisywalne_i_niezmienialne(admin_client, model):
    """Odblokowaliśmy kasowanie, ale reszta kontraktu read-only ma zostać."""
    ma = site.get_model_admin(model)
    request = admin_client.request(PATH_INFO="/").wsgi_request

    assert ma.has_add_permission(request) is False
    assert ma.has_change_permission(request) is False
