"""Testy widoków changelist + `get_object` / `get_actions` adminów."""

import pytest
from django.contrib.admin import AdminSite
from django.urls import reverse
from model_bakery import baker

from bpp.models import Dyscyplina_Zrodla, Wydawnictwo_Ciagle
from rozbieznosci_dyscyplin.admin import RozbieznosciViewAdmin
from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView


def test_RozbieznosciAutorZrodloAdmin(admin_app):
    res = admin_app.get(
        reverse("admin:rozbieznosci_dyscyplin_rozbieznoscizrodelview_changelist")
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rozbieznosci_view_admin_changelist_loads(admin_app):
    """Test RozbieznosciViewAdmin changelist page loads."""
    res = admin_app.get(
        reverse("admin:rozbieznosci_dyscyplin_rozbieznosciview_changelist")
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rozbieznosci_view_admin_get_object(zle_przypisana_praca, rf):
    """Test RozbieznosciViewAdmin.get_object with tuple PK."""
    rozbieznosc = RozbieznosciView.objects.first()
    assert rozbieznosc is not None

    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")

    pk_str = str(rozbieznosc.pk)
    obj = ra.get_object(req, pk_str)

    assert obj is not None
    assert obj.pk == rozbieznosc.pk


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_admin_get_object(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
    rf,
):
    """Test RozbieznosciZrodelViewAdmin.get_object with 4-tuple PK."""
    from rozbieznosci_dyscyplin.admin import RozbieznosciZrodelViewAdmin

    # Utworz rozbieznosc zrodel
    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    wc.dodaj_autora(autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1)

    rozbieznosc = RozbieznosciZrodelView.objects.first()
    assert rozbieznosc is not None

    ra = RozbieznosciZrodelViewAdmin(RozbieznosciZrodelView, AdminSite())
    req = rf.get("/")

    pk_str = str(rozbieznosc.pk)
    obj = ra.get_object(req, pk_str)

    assert obj is not None
    assert obj.pk == rozbieznosc.pk


@pytest.mark.django_db
def test_rozbieznosci_view_admin_get_actions(rf):
    """Test RozbieznosciViewAdmin.get_actions returns both actions."""
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")

    actions = ra.get_actions(req)

    assert "ustaw_pierwsza" in actions
    assert "ustaw_druga" in actions
