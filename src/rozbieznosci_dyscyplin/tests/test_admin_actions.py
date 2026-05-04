"""Testy akcji adminowych: ustaw_pierwsza/druga_dyscypline, przypisz_wszystkim,
oraz pomocniczych funkcji ustaw_dyscypline / real_ustaw_dyscypline."""

import pytest
from django.contrib.admin import AdminSite
from django.contrib.messages import get_messages

from bpp.models import Autor_Dyscyplina
from rozbieznosci_dyscyplin.admin import (
    DYSCYPLINA_AUTORA,
    RozbieznosciViewAdmin,
    ustaw_druga_dyscypline,
    ustaw_pierwsza_dyscypline,
)
from rozbieznosci_dyscyplin.models import RozbieznosciView

from .conftest import middleware


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_pierwsza(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_pierwsza_dyscypline(None, req, None)
        msg = get_messages(req)

    assert RozbieznosciView.objects.count() == 0
    assert "ustawiono dyscyplinę" in list(msg)[0].message


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_druga(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_druga_dyscypline(None, req, None)
        assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_pusta_druga(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1

    ad = Autor_Dyscyplina.objects.get(
        autor=zle_przypisana_praca.autorzy.first(), rok=zle_przypisana_praca.rok
    )
    ad.subdyscyplina_naukowa = None
    ad.save()

    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_druga_dyscypline(None, req, None)
        msg = get_messages(req)

    assert "jest żadna" in list(msg)[0].message
    assert RozbieznosciView.objects.count() == 1


def test_RozbieznosciDyscyplinAdmin_przypisz_pierwsza_wszystkim(
    zle_przypisana_praca, rf, dyscyplina1
):
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")
    with middleware(req):
        ra.przypisz_wszystkim(req)
    assert RozbieznosciView.objects.count() == 0
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_przypisz_druga_wszystkim(
    zle_przypisana_praca, rf, dyscyplina2
):
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")
    with middleware(req):
        ra.przypisz_druga_wszystkim(req)
    assert RozbieznosciView.objects.count() == 0
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


@pytest.mark.django_db
def test_ustaw_dyscypline_empty_selection(rf):
    """Test ustaw_dyscypline with empty selection shows warning."""
    from rozbieznosci_dyscyplin.admin import ustaw_dyscypline

    req = rf.post("/", data={"_selected_action": []})

    with middleware(req):
        ustaw_dyscypline(DYSCYPLINA_AUTORA, None, req, None)
        msgs = list(get_messages(req))

    assert len(msgs) == 1
    assert "nic nie zostało zaznaczone" in msgs[0].message


@pytest.mark.django_db
def test_ustaw_dyscypline_with_select_across(zle_przypisana_praca, rf, dyscyplina1):
    """Test ustaw_dyscypline with select_across=1."""
    from rozbieznosci_dyscyplin.admin import ustaw_dyscypline

    req = rf.post("/", data={"select_across": "1", "_selected_action": []})

    with middleware(req):
        ustaw_dyscypline(DYSCYPLINA_AUTORA, None, req, RozbieznosciView.objects.all())

    assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_przypisz_wszystkim_empty_queryset(rf):
    """Test przypisz_wszystkim with empty queryset shows warning."""
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")

    with middleware(req):
        response = ra.przypisz_wszystkim(req)
        msgs = list(get_messages(req))

    assert response.status_code == 302
    assert len(msgs) == 1
    assert "nie stwierdzono rekordów" in msgs[0].message


@pytest.mark.django_db
def test_real_ustaw_dyscypline_handles_missing_record(rf):
    """Test real_ustaw_dyscypline handles deleted record during processing."""
    from rozbieznosci_dyscyplin.admin import ResultNotifier, real_ustaw_dyscypline

    # Przekaz nieistniejace PK
    notifier = ResultNotifier()
    real_ustaw_dyscypline(DYSCYPLINA_AUTORA, [[999, 999, 999]], notifier)

    assert len(notifier.retbuf) == 1
    assert "zmieniła się podczas operacji" in notifier.retbuf[0]
