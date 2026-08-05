import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowOdpiecie


def _odpiecie(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    imp = baker.make(ImportPracownikow, owner=owner, stan=stan)
    aj = baker.make(Autor_Jednostka, autor__nazwisko="Testowski")
    odp = ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    return imp, odp


@pytest.mark.django_db
def test_zaznaczenie_odpiecia_ustawia_flage(admin_client, admin_user):
    imp, odp = _odpiecie(admin_user)
    url = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    resp = admin_client.post(url, {"zaznaczone": "on"})
    assert resp.status_code == 200
    assert b"Testowski" in resp.content
    odp.refresh_from_db()
    assert odp.zaznaczone is True

    resp = admin_client.post(url, {})
    odp.refresh_from_db()
    assert odp.zaznaczone is False


@pytest.mark.django_db
def test_odpiecie_blokada_poza_podgladem(admin_client, admin_user):
    imp, odp = _odpiecie(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    url = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    resp = admin_client.post(url, {"zaznaczone": "on"})
    assert resp.status_code == 400
    odp.refresh_from_db()
    assert odp.zaznaczone is False


@pytest.mark.django_db
def test_odpiecie_cudzy_import_404(client, django_user_model, admin_user):
    imp, odp = _odpiecie(admin_user)
    obcy = django_user_model.objects.create_user(
        username="obcy", password="x", is_superuser=False
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    obcy.groups.add(grupa)
    client.force_login(obcy)
    url = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    resp = client.post(url, {"zaznaczone": "on"})
    assert resp.status_code == 404
