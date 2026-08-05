"""Izolacja multi-host importera publikacji (uwagi #2/#3 reviewera).

Redaktor jednej uczelni nie może odczytać ani zmodyfikować sesji / paczki /
wpisu paczki innej uczelni po samym ``pk`` (dotąd ``get_object_or_404`` po pk
bez filtra uczelni = IDOR). Superuser widzi wszystko; przy jednej uczelni
warsztat pozostaje współdzielony (bez zmiany zachowania).
"""

import pytest
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from importer_publikacji.models import (
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)


@pytest.fixture
def uczelnia_b(db):
    from bpp.models import Uczelnia

    site_b = Site.objects.create(domain="uczelnia-b.example.com", name="B")
    return Uczelnia.objects.create(nazwa="Uczelnia B", skrot="BB", site=site_b)


def _redaktor(django_user_model):
    u = baker.make(django_user_model, is_superuser=False, is_staff=True)
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grp)
    return u


def _redaktor_client(django_user_model, client):
    client.force_login(_redaktor(django_user_model))
    return client


def _sesja(uczelnia, django_user_model, **kwargs):
    return baker.make(
        ImportSession,
        uczelnia=uczelnia,
        created_by=baker.make(django_user_model),
        **kwargs,
    )


def _task_status_url(session):
    return reverse("importer_publikacji:task-status", kwargs={"session_id": session.pk})


@pytest.mark.django_db
def test_task_status_obca_uczelnia_404(client, django_user_model, uczelnia, uczelnia_b):
    # uczelnia (A) = bieżący Site. Sesja należy do B.
    sesja_b = _sesja(
        uczelnia_b, django_user_model, status=ImportSession.Status.FETCHING
    )
    c = _redaktor_client(django_user_model, client)
    assert c.get(_task_status_url(sesja_b)).status_code == 404


@pytest.mark.django_db
def test_task_status_wlasna_uczelnia_widoczna(
    client, django_user_model, uczelnia, uczelnia_b
):
    # Kontrola pozytywna: sesja uczelni A (nawet cudza) jest widoczna —
    # warsztat współdzielony w obrębie uczelni.
    sesja_a = _sesja(uczelnia, django_user_model, status=ImportSession.Status.FETCHING)
    c = _redaktor_client(django_user_model, client)
    assert c.get(_task_status_url(sesja_a)).status_code == 200


@pytest.mark.django_db
def test_superuser_widzi_obca_uczelnie(client, django_user_model, uczelnia, uczelnia_b):
    sesja_b = _sesja(
        uczelnia_b, django_user_model, status=ImportSession.Status.FETCHING
    )
    su = baker.make(django_user_model, is_superuser=True, is_staff=True)
    client.force_login(su)
    assert client.get(_task_status_url(sesja_b)).status_code == 200


@pytest.mark.django_db
def test_jedna_uczelnia_bez_izolacji(client, django_user_model, uczelnia):
    # Tylko jedna uczelnia → tylko_jedna_uczelnia() → scoping no-op. Sesja bez
    # uczelni (legacy/None) nadal widoczna dla redaktora (współdzielony warsztat).
    sesja = _sesja(None, django_user_model, status=ImportSession.Status.FETCHING)
    c = _redaktor_client(django_user_model, client)
    assert c.get(_task_status_url(sesja)).status_code == 200


@pytest.mark.django_db
def test_batch_detail_obca_uczelnia_404(
    client, django_user_model, uczelnia, uczelnia_b
):
    batch_b = baker.make(MultipleWorksImport, uczelnia=uczelnia_b)
    c = _redaktor_client(django_user_model, client)
    url = reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch_b.pk})
    assert c.get(url).status_code == 404


@pytest.mark.django_db
def test_batch_entry_skip_obca_uczelnia_404(
    client, django_user_model, uczelnia, uczelnia_b
):
    batch_b = baker.make(MultipleWorksImport, uczelnia=uczelnia_b)
    entry_b = baker.make(
        MultipleWorksImportEntry,
        parent=batch_b,
        order=0,
    )
    c = _redaktor_client(django_user_model, client)
    url = reverse(
        "importer_publikacji:batch-entry-skip", kwargs={"entry_id": entry_b.pk}
    )
    assert c.post(url).status_code == 404


@pytest.mark.django_db
def test_lista_sesji_wyklucza_obca_uczelnie(
    client, django_user_model, uczelnia, uczelnia_b
):
    sesja_a = _sesja(uczelnia, django_user_model, status=ImportSession.Status.FETCHING)
    sesja_b = _sesja(
        uczelnia_b, django_user_model, status=ImportSession.Status.FETCHING
    )
    c = _redaktor_client(django_user_model, client)
    resp = c.get(reverse("importer_publikacji:sessions"))
    assert resp.status_code == 200
    widoczne = {s.pk for s in resp.context["sessions"]}
    assert sesja_a.pk in widoczne
    assert sesja_b.pk not in widoczne
