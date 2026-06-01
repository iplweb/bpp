import pytest
from django.urls import reverse

from snapshot_odpiec.models import SnapshotOdpiec, WartoscSnapshotu


@pytest.mark.django_db
def test_SnapshotOdpiecManager_create(
    wydawnictwo_ciagle_z_dwoma_autorami,
    wydawnictwo_zwarte_z_autorem,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    admin_user,
):

    obj = SnapshotOdpiec.objects.create(owner=admin_user)

    assert WartoscSnapshotu.objects.filter(parent=obj).count() == 1


@pytest.mark.django_db
def test_SnapshotOdpiecManager_apply(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    admin_user,
):
    wzad = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.first()
    wzad.przypieta = True
    wzad.save()

    obj = SnapshotOdpiec.objects.create(owner=admin_user)
    assert WartoscSnapshotu.objects.filter(parent=obj).count() == 1

    wzad = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.autorzy_set.first()
    wzad.przypieta = False
    wzad.save()

    obj.apply()

    wzad.refresh_from_db()
    assert wzad.przypieta


@pytest.mark.django_db
def test_snapshot_odpiec_index_empty(admin_client):
    url = reverse("snapshot_odpiec:index")
    res = admin_client.get(url)
    assert res.status_code == 200


@pytest.mark.django_db
def test_snapshot_odpiec_index_one_time(admin_client, admin_user):
    SnapshotOdpiec.objects.create(owner=admin_user)
    url = reverse("snapshot_odpiec:index")
    res = admin_client.get(url)
    assert res.status_code == 200


@pytest.mark.django_db
def test_snapshot_odpiec_nowy_get_shows_confirmation(admin_app):
    """GET wyświetla ekran potwierdzenia, NIE tworzy snapshotu."""
    url = reverse("snapshot_odpiec:nowy")
    res = admin_app.get(url)
    assert res.status_code == 200
    assert SnapshotOdpiec.objects.count() == 0


@pytest.mark.django_db
def test_snapshot_odpiec_nowy_post_creates(admin_app):
    """POST tworzy snapshot."""
    url = reverse("snapshot_odpiec:nowy")
    form = admin_app.get(url).forms["nowy-confirm"]
    res = form.submit().maybe_follow()
    assert b"Utworzono snapshot" in res.content
    assert SnapshotOdpiec.objects.count() == 1


@pytest.mark.django_db
def test_snapshot_odpiec_aplikuj_get_shows_confirmation(
    admin_app, admin_user, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
):
    """GET wyświetla potwierdzenie, NIE aplikuje snapshotu."""
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.autorzy_set.update(przypieta=False)
    so = SnapshotOdpiec.objects.create(owner=admin_user)
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.autorzy_set.update(przypieta=True)

    url = reverse("snapshot_odpiec:aplikuj", args=(so.pk,))
    res = admin_app.get(url)
    assert res.status_code == 200

    # GET nie zmienił stanu przypięć
    x = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.autorzy_set.first()
    x.refresh_from_db()
    assert x.przypieta is True


@pytest.mark.django_db
def test_snapshot_odpiec_aplikuj_post_applies(
    admin_app, admin_user, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
):
    """POST aplikuje snapshot na bazę."""
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.autorzy_set.update(przypieta=False)
    so = SnapshotOdpiec.objects.create(owner=admin_user)
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.autorzy_set.update(przypieta=True)

    url = reverse("snapshot_odpiec:aplikuj", args=(so.pk,))
    form = admin_app.get(url).forms["aplikuj-confirm"]
    res = form.submit().maybe_follow()
    assert res.status_code == 200
    assert b"Zaaplikowano snapshot" in res.content
    x = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina.autorzy_set.first()
    x.refresh_from_db()
    assert x.przypieta is False
