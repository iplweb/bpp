"""Testy akcji adminowych: ustaw_pierwsza/druga_dyscypline, przypisz_wszystkim,
oraz pomocniczych funkcji ustaw_dyscypline / real_ustaw_dyscypline."""

import pytest
from django.contrib.messages import get_messages

from bpp.models import Autor_Dyscyplina
from rozbieznosci_dyscyplin.admin import (
    DYSCYPLINA_AUTORA,
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

    assert "nie ma drugiej dyscypliny za rok" in list(msg)[0].message
    assert RozbieznosciView.objects.count() == 1


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
def test_real_ustaw_dyscypline_handles_missing_record(rf):
    """Test real_ustaw_dyscypline handles deleted record during processing."""
    from rozbieznosci_dyscyplin.admin import ResultNotifier, real_ustaw_dyscypline

    # Przekaz nieistniejace PK
    notifier = ResultNotifier()
    real_ustaw_dyscypline(DYSCYPLINA_AUTORA, [[999, 999, 999]], notifier)

    assert len(notifier.retbuf) == 1
    assert "zmieniła się podczas operacji" in notifier.retbuf[0]


@pytest.mark.django_db
def test_akcja_zachowuje_filtry(zle_przypisana_praca, rf):
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post(
        "/admin/x/?rok=2022&pracuje_na_uczelni=tak", data={"_selected_action": [pk]}
    )

    with middleware(req):
        res = ustaw_pierwsza_dyscypline(None, req, None)

    assert res.status_code == 302
    assert res.url == "/admin/x/?rok=2022&pracuje_na_uczelni=tak"


@pytest.mark.django_db
def test_real_ustaw_dyscypline_validation_error(zle_przypisana_praca, mocker):
    """A record that fails validation is skipped with a warning, not a 500."""
    from django.core.exceptions import ValidationError

    from bpp.models import Wydawnictwo_Ciagle_Autor
    from rozbieznosci_dyscyplin.admin import ResultNotifier, real_ustaw_dyscypline

    mocker.patch.object(
        Wydawnictwo_Ciagle_Autor,
        "save",
        side_effect=ValidationError("Zły procent udziału"),
    )
    notifier = ResultNotifier()
    pk = RozbieznosciView.objects.first().pk
    real_ustaw_dyscypline(DYSCYPLINA_AUTORA, [pk], notifier)

    assert len(notifier.retbuf) == 1
    assert "nie przechodzi walidacji" in notifier.retbuf[0]
    assert "Zły procent udziału" in notifier.retbuf[0]
    assert RozbieznosciView.objects.count() == 1
