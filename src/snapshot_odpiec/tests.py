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


@pytest.fixture
def prace_w_dwoch_okresach(
    autor_jan_kowalski, jednostka, dyscyplina1, typy_odpowiedzialnosci
):
    """Dwie prace z dyscypliną: z 2023 (okres 2022–2025) i 2027 (2026–2030)."""
    from model_bakery import baker

    from bpp.models import Autor_Dyscyplina, Wydawnictwo_Ciagle

    prace = {}
    for rok in (2023, 2027):
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        wc = baker.make(Wydawnictwo_Ciagle, rok=rok)
        prace[rok] = wc.dodaj_autora(
            autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
        )
    return prace


@pytest.mark.django_db
def test_snapshot_z_okresem_obejmuje_tylko_lata_okresu(
    prace_w_dwoch_okresach, admin_user
):
    from ewaluacja_common.models import OkresEwaluacji

    okres = OkresEwaluacji.objects.get(rok_od=2022)
    snap = SnapshotOdpiec.objects.create(owner=admin_user, okres=okres)
    assert set(snap.wartoscsnapshotu_set.values_list("object_id", flat=True)) == {
        prace_w_dwoch_okresach[2023].pk
    }

    # Snapshot bez okresu (stary) — wszystkie lata.
    caly = SnapshotOdpiec.objects.create(owner=admin_user)
    assert caly.calosc() == 2


@pytest.mark.django_db
def test_aplikacja_snapshotu_okresu_nie_rusza_innego_okresu(
    prace_w_dwoch_okresach, admin_user
):
    from ewaluacja_common.models import OkresEwaluacji

    stara, nowa = prace_w_dwoch_okresach[2023], prace_w_dwoch_okresach[2027]
    snap = SnapshotOdpiec.objects.create(
        owner=admin_user, okres=OkresEwaluacji.objects.get(rok_od=2022)
    )
    type(stara).objects.filter(pk__in=[stara.pk, nowa.pk]).update(przypieta=False)

    snap.apply()

    stara.refresh_from_db()
    nowa.refresh_from_db()
    assert stara.przypieta is True  # przywrócona ze snapshotu
    assert nowa.przypieta is False  # inny okres — bez zmian


@pytest.mark.django_db
def test_lista_i_nowy_snapshot_wg_wybranego_okresu(admin_client, admin_user):
    """Lista: snapshoty okresu z paska + stare (bez okresu); nowy snapshot
    dostaje okres z paska."""
    from ewaluacja_common.models import OkresEwaluacji

    o2022 = OkresEwaluacji.objects.get(rok_od=2022)
    o2026 = OkresEwaluacji.objects.get(rok_od=2026)
    s2022 = SnapshotOdpiec.objects.create(owner=admin_user, okres=o2022)
    stary = SnapshotOdpiec.objects.create(owner=admin_user)
    admin_client.post(reverse("ewaluacja_common:wybierz_okres"), {"okres": o2026.pk})

    lista = admin_client.get(reverse("snapshot_odpiec:index"))
    widoczne = {s.pk for s in lista.context["object_list"]}
    assert stary.pk in widoczne
    assert s2022.pk not in widoczne
    assert 'class="pasek-okresu"' in lista.content.decode()

    admin_client.post(reverse("snapshot_odpiec:nowy"))
    assert SnapshotOdpiec.objects.latest("pk").okres == o2026
