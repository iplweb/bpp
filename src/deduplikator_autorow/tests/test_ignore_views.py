import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from deduplikator_autorow.models import IgnoredAuthor, IgnoredScientist


@pytest.fixture
def auth_client(client, db):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx")
    user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_ignore_scientist_endpoint(auth_client):
    sci = baker.make("pbn_api.Scientist")
    response = auth_client.post(
        reverse("deduplikator_autorow:ignore_scientist"),
        {"scientist_id": sci.pk, "reason": "test"},
    )
    assert response.status_code == 302
    assert IgnoredScientist.objects.filter(scientist=sci).exists()


@pytest.mark.django_db
def test_ignore_autor_endpoint(auth_client):
    autor = baker.make("bpp.Autor")
    response = auth_client.post(
        reverse("deduplikator_autorow:ignore_autor"),
        {"autor_id": autor.pk, "reason": "test"},
    )
    assert response.status_code == 302
    assert IgnoredAuthor.objects.filter(autor=autor).exists()


@pytest.mark.django_db
def test_reset_ignored_autorzy_endpoint(auth_client):
    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser")
    IgnoredAuthor.objects.create(autor=autor, created_by=user)
    response = auth_client.post(reverse("deduplikator_autorow:reset_ignored_autorzy"))
    assert response.status_code == 302
    assert IgnoredAuthor.objects.count() == 0


@pytest.mark.django_db
def test_reset_ignored_scientists_endpoint(auth_client):
    sci = baker.make("pbn_api.Scientist")
    user = baker.make("bpp.BppUser")
    IgnoredScientist.objects.create(scientist=sci, created_by=user)
    response = auth_client.post(
        reverse("deduplikator_autorow:reset_ignored_scientists")
    )
    assert response.status_code == 302
    assert IgnoredScientist.objects.count() == 0
