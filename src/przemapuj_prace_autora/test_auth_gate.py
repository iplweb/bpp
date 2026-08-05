"""#514 F-1: przemapowanie/cofanie prac autora między jednostkami to akcje
w skali całego dorobku autora — muszą być za bramką grupy „wprowadzanie
danych", nie za samym ``login_required`` (dowolny zalogowany user).
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, Jednostka
from przemapuj_prace_autora.models import PrzemapoaniePracAutora

User = get_user_model()


def _przemapowanie():
    return PrzemapoaniePracAutora.objects.create(
        autor=baker.make(Autor),
        jednostka_z=baker.make(Jednostka),
        jednostka_do=baker.make(Jednostka),
    )


def _klient(username, *, grupa=False):
    u = User.objects.create_user(username=username, password="pass")
    if grupa:
        g, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        u.groups.add(g)
    c = Client()
    c.login(username=username, password="pass")
    return c


@pytest.mark.django_db
def test_cofnij_bez_grupy_403():
    prz = _przemapowanie()
    url = reverse("przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk})
    resp = _klient("plain").post(url)
    # 403 z braces (zalogowany, zła grupa) — bramka odcięła PRZED service.cofnij.
    assert resp.status_code == 403


@pytest.mark.django_db
def test_cofnij_z_grupa_przechodzi():
    prz = _przemapowanie()
    url = reverse("przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk})
    resp = _klient("entry", grupa=True).post(url)
    # członek grupy przechodzi bramkę: cofnij wykonuje się i redirectuje (302).
    assert resp.status_code == 302


@pytest.mark.django_db
def test_przemapuj_prace_bez_grupy_403():
    autor = baker.make(Autor)
    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )
    assert _klient("plain2").get(url).status_code == 403


@pytest.mark.django_db
def test_wybierz_autora_bez_grupy_403():
    url = reverse("przemapuj_prace_autora:wybierz_autora")
    assert _klient("plain3").get(url).status_code == 403
