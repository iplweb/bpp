"""FD#640 — raport slotów autora nie przyjmuje autora spoza uczelni."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka
from raport_slotow import const
from raport_slotow.forms.autor import AutorRaportSlotowForm
from raport_slotow.views import SESSION_KEY

KOMUNIKAT = "jest autorem spoza uczelni"


@pytest.fixture
def autor_obcy(uczelnia_z_obca_jednostka, obca_jednostka):
    autor = baker.make(Autor, imiona="Ewa", nazwisko="Obca")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    return autor


@pytest.fixture
def autor_nasz(uczelnia_z_obca_jednostka, jednostka):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Nasz")
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    return autor


def _dane(autor, rok):
    return {
        "obiekt": autor.pk,
        "od_roku": rok,
        "do_roku": rok,
        "dzialanie": const.DZIALANIE_WSZYSTKO,
        "minimalny_pk": 0,
        "slot": "",
        "_export": "html",
    }


@pytest.mark.django_db
def test_fd640_formularz_odrzuca_autora_spoza_uczelni(admin_client, autor_obcy, rok):
    res = admin_client.post(reverse("raport_slotow:index"), _dane(autor_obcy, rok))
    assert res.status_code == 200  # formularz z błędem, bez przekierowania
    assert KOMUNIKAT in res.content.decode("utf-8")
    assert SESSION_KEY not in admin_client.session


@pytest.mark.django_db
def test_fd640_formularz_przyjmuje_autora_uczelni(admin_client, autor_nasz, rok):
    res = admin_client.post(reverse("raport_slotow:index"), _dane(autor_nasz, rok))
    assert res.status_code == 302


@pytest.mark.django_db
def test_fd640_raport_z_sesji_dla_obcego_nie_powstaje(admin_client, autor_obcy, rok):
    """Stara sesja / zakładka: widok raportu waliduje tak samo jak formularz."""
    dane = _dane(autor_obcy, rok)
    dane["slot"] = None
    s = admin_client.session
    s.update({SESSION_KEY: dane})
    s.save()
    res = admin_client.get(reverse("raport_slotow:raport"))
    assert res.status_code == 302


@pytest.mark.django_db
def test_fd640_formularz_bez_uczelni_nie_odrzuca(autor_obcy, rok):
    dane = _dane(autor_obcy, rok)
    assert AutorRaportSlotowForm(dane).is_valid()
    assert not AutorRaportSlotowForm(
        dane, uczelnia=autor_obcy.autor_jednostka_set.first().jednostka.uczelnia
    ).is_valid()
