"""Podstrona „Ludzie spoza XLS" (OdpieciaView, T2.3) + regresje nawigacji."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowOdpiecie


def _imp(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    return baker.make(
        ImportPracownikow, owner=owner, stan=stan, finished_successfully=True
    )


def _odpiecie(imp):
    aj = baker.make(Autor_Jednostka, autor__nazwisko="Odpietowski")
    return ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)


def _url(imp):
    return reverse("import_pracownikow:odpiecia", kwargs={"pk": imp.pk})


@pytest.mark.django_db
def test_odpiecia_renderuje_tabele(admin_client, admin_user):
    imp = _imp(admin_user)
    odp = _odpiecie(imp)
    resp = admin_client.get(_url(imp))
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert "Odpietowski" in tresc
    # toggle checkboxa (przelacz-odpiecie) obecny (import w podglądzie)
    assert (
        reverse(
            "import_pracownikow:przelacz-odpiecie",
            kwargs={"pk": imp.pk, "odp_pk": odp.pk},
        )
        in tresc
    )


@pytest.mark.django_db
def test_odpiecia_datatables_init(admin_client, admin_user):
    """Tabela odpięć ma id + inicjalizację DataTables (client-side filtr/sort)."""
    imp = _imp(admin_user)
    _odpiecie(imp)
    tresc = admin_client.get(_url(imp)).content.decode("utf-8")
    assert 'id="tabela-odpiec"' in tresc
    assert ".DataTable(" in tresc


@pytest.mark.django_db
def test_odpiecia_puste_callout(admin_client, admin_user):
    imp = _imp(admin_user)
    resp = admin_client.get(_url(imp))
    assert resp.status_code == 200
    assert "Brak powiązań" in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_odpiecia_przelacz_dziala(admin_client, admin_user):
    imp = _imp(admin_user)
    odp = _odpiecie(imp)
    url = reverse(
        "import_pracownikow:przelacz-odpiecie",
        kwargs={"pk": imp.pk, "odp_pk": odp.pk},
    )
    resp = admin_client.post(url, {"zaznaczone": "on"})
    assert resp.status_code == 200
    odp.refresh_from_db()
    assert odp.zaznaczone is True


@pytest.mark.django_db
def test_odpiecia_ma_link_wroc_do_przegladu(admin_client, admin_user):
    imp = _imp(admin_user)
    resp = admin_client.get(_url(imp))
    tresc = resp.content.decode("utf-8")
    assert reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk}) in tresc


@pytest.mark.django_db
def test_odpiecia_scoping_obcy_import_404(client, django_user_model, admin_user):
    imp = _imp(admin_user)
    obcy = django_user_model.objects.create_user(
        username="obcy_odp_view", password="x", is_superuser=False
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    obcy.groups.add(grupa)
    client.force_login(obcy)
    resp = client.get(_url(imp))
    assert resp.status_code == 404


# --- Regresja: results NIE renderuje już sekcji odpięć --------------------


@pytest.mark.django_db
def test_results_nie_renderuje_sekcji_odpiec(admin_client, admin_user):
    imp = _imp(admin_user)
    _odpiecie(imp)
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    # nagłówek sekcji odpięć przeniesiony do OdpieciaView — tu nieobecny
    assert "spoza tego pliku (odpięcia)" not in tresc
    assert "Odpietowski" not in tresc


# --- Regresja: podstrony mają link „wróć do przeglądu" --------------------


@pytest.mark.django_db
def test_results_ma_link_wroc_do_przegladu(admin_client, admin_user):
    imp = _imp(admin_user)
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk}) in tresc


@pytest.mark.django_db
def test_jednostki_ma_link_wroc_do_przegladu(admin_client, admin_user):
    imp = _imp(admin_user)
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk}) in tresc


@pytest.mark.django_db
def test_tytuly_ma_link_wroc_do_przegladu(admin_client, admin_user):
    imp = _imp(admin_user)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    tresc = admin_client.get(url).content.decode("utf-8")
    assert reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk}) in tresc
