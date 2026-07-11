import pytest
from django.contrib.auth.models import AnonymousUser
from model_bakery import baker
from rest_framework.test import APIClient

from api_v1.permissions import MoznaUzywacZapytania
from bpp.const import GR_WPROWADZANIE_DANYCH


class _FakeRequest:
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
def test_gate_anon_odrzucony():
    assert (
        MoznaUzywacZapytania().has_permission(_FakeRequest(AnonymousUser()), None)
        is False
    )


@pytest.mark.django_db
def test_gate_superuser_przechodzi():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is True


@pytest.mark.django_db
def test_gate_staff_w_grupie_przechodzi():
    from django.contrib.auth.models import Group

    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is True


@pytest.mark.django_db
def test_gate_zwykly_zalogowany_odrzucony():
    u = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is False


def _staff_client():
    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=True)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


@pytest.mark.django_db
def test_zapytanie_rekord_anon_403():
    resp = APIClient().get("/api/v1/zapytanie/rekord/", {"q": "rok = 2024"})
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_zapytanie_rekord_puste_q_zwraca_pusto():
    resp = _staff_client().get("/api/v1/zapytanie/rekord/", {"q": ""})
    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_zapytanie_rekord_bledne_q_400():
    resp = _staff_client().get(
        "/api/v1/zapytanie/rekord/", {"q": "nieistniejace_pole = 1"}
    )
    assert resp.status_code == 400
    assert "error" in resp.data
