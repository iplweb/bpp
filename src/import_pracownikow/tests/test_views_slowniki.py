import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowStopien,
)


@pytest.fixture
def owner(django_user_model):
    u = baker.make(django_user_model)
    grp, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    u.groups.add(grp)
    return u


@pytest.mark.django_db
def test_ekran_stopni_get_200(client, owner):
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow,
        owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="kpt.",
        tryb=ImportPracownikowStopien.TRYB_BRAK,
    )
    resp = client.get(reverse("import_pracownikow:stopnie", kwargs={"pk": imp.pk}))
    assert resp.status_code == 200
    assert "kpt." in resp.content.decode()


@pytest.mark.django_db
def test_ekran_stanowisk_get_200(client, owner):
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow,
        owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    resp = client.get(reverse("import_pracownikow:stanowiska", kwargs={"pk": imp.pk}))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_post_zapisuje_decyzje_stopnia_akceptuj(client, owner):
    # Mirror test_views_tytuly.test_post_zapisuje_decyzje_* — POST decyzji
    # (akceptuj) redirectuje i zapisuje `decyzja`.
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow,
        owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    dec = baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="mł. bryg.",
        tryb=ImportPracownikowStopien.TRYB_BRAK,
        decyzja=ImportPracownikowStopien.DECYZJA_MAPUJ,
    )
    resp = client.post(
        reverse("import_pracownikow:stopnie", kwargs={"pk": imp.pk}),
        {f"dec_{dec.pk}_decyzja": ImportPracownikowStopien.DECYZJA_AKCEPTUJ},
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert dec.decyzja == ImportPracownikowStopien.DECYZJA_AKCEPTUJ


@pytest.mark.django_db
def test_post_mapuj_bez_celu_daje_blad_i_nie_zapisuje(client, owner):
    # Mirror walidacji „mapuj bez wybranego celu" — POST z decyzją MAPUJ i pustym
    # celem redirectuje z komunikatem błędu i NIE zapisuje decyzji.
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow,
        owner=owner,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    dec = baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="kpt.",
        tryb=ImportPracownikowStopien.TRYB_ZGADYWANIE,
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
    )
    resp = client.post(
        reverse("import_pracownikow:stopnie", kwargs={"pk": imp.pk}),
        {
            f"dec_{dec.pk}_decyzja": ImportPracownikowStopien.DECYZJA_MAPUJ,
            f"dec_{dec.pk}_wybrana": "",
        },
    )
    assert resp.status_code == 302  # redirect z komunikatem błędu
    dec.refresh_from_db()
    # walidacja odrzuciła zapis — decyzja NIE zmieniona na MAPUJ
    assert dec.decyzja == ImportPracownikowStopien.DECYZJA_AKCEPTUJ


@pytest.mark.django_db
def test_zatwierdz_pelny_blokuje_gdy_stopnie_nierozstrzygniete(client, owner):
    client.force_login(owner)
    imp = baker.make(
        ImportPracownikow,
        owner=owner,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
    )
    baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="kpt.",
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
        utworzony=None,
    )
    resp = client.post(
        reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk}),
        {"zakres": "pelny"},
    )
    assert resp.status_code == 400


def test_mapowanie_form_ma_toggle_slownikow():
    from import_pracownikow.forms import MapowanieForm

    f = MapowanieForm(naglowki=["nazwisko"])
    assert "tworz_brakujace_stopnie" in f.fields
    assert "tworz_brakujace_stanowiska" in f.fields
