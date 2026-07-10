import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from przemapuj_prace_autora import service
from przemapuj_prace_autora.models import PrzemapoaniePracAutora

User = get_user_model()


@pytest.fixture
def kl(db):
    User.objects.create_user(
        username="cof", password="pass", is_staff=True, is_superuser=True
    )
    c = Client()
    c.login(username="cof", password="pass")
    return c


@pytest.mark.django_db
def test_cofnij_view_przywraca_i_redirect(kl):
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    jz = baker.make(Jednostka, nazwa="Stara", skrot="ST")
    jd = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A", rok=2023)
    pa = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jz)
    prz = service.przemapuj(autor, jz, jd, user=None)
    pa.refresh_from_db()
    assert pa.jednostka_id == jd.pk

    url = reverse("przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk})
    resp = kl.post(url)
    assert resp.status_code == 302
    pa.refresh_from_db()
    assert pa.jednostka_id == jz.pk
    # rekord audytu NIE skasowany
    assert PrzemapoaniePracAutora.objects.filter(pk=prz.pk).exists()


@pytest.mark.django_db
def test_cofnij_view_odrzuca_get(kl):
    autor = baker.make(Autor)
    prz = PrzemapoaniePracAutora.objects.create(
        autor=autor,
        jednostka_z=baker.make(Jednostka),
        jednostka_do=baker.make(Jednostka),
    )
    url = reverse("przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk})
    resp = kl.get(url)
    assert resp.status_code == 405
