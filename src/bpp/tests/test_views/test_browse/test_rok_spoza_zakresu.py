"""Rollbar #5358: rekord z rokiem 212 (literówka w danych) wywalał
``/bpp/lata/`` z ``NoReverseMatch``, bo URL ``browse_rok`` przyjmował
wyłącznie 4 cyfry. Strona roku wpuszcza teraz każdy rok obecny w danych.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.views.browse import LataView
from fixtures.conftest_multisite import make_request_for_site


@pytest.fixture
def praca_z_roku_212(
    uczelnia1, site1, jednostka_uczelnia1, autor_uczelnia1, typy_odpowiedzialnosci
):
    praca = baker.make(
        "bpp.Wydawnictwo_Ciagle", rok=212, tytul_oryginalny="Praca z roku 212"
    )
    praca.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    return praca


@pytest.mark.django_db
def test_lata_renderuje_sie_z_rokiem_trzycyfrowym(
    client, site1, praca_z_roku_212, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    res = client.get(reverse("bpp:browse_lata"), HTTP_HOST=site1.domain)
    assert res.status_code == 200
    assert reverse("bpp:browse_rok", args=(212,)) in res.content.decode()


@pytest.mark.django_db
def test_lata_grupuje_rok_212_w_dekadzie_210(site1, praca_z_roku_212, settings):
    settings.ALLOWED_HOSTS = ["*"]
    view = LataView()
    view.request = make_request_for_site(site1)
    view.kwargs = {}
    view.object_list = view.get_queryset()
    ctx = view.get_context_data()
    assert [y["year"] for y in ctx["decades"][210]] == [212]


@pytest.mark.django_db
def test_rok_trzycyfrowy_z_danymi_daje_200(client, site1, praca_z_roku_212, settings):
    settings.ALLOWED_HOSTS = ["*"]
    res = client.get(reverse("bpp:browse_rok", args=(212,)), HTTP_HOST=site1.domain)
    assert res.status_code == 200
    assert "Praca z roku 212" in res.content.decode()


@pytest.mark.django_db
def test_rok_trzycyfrowy_ma_link_do_sasiedniego_roku(
    client, site1, praca_z_roku_212, jednostka_uczelnia1, autor_uczelnia1, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    druga = baker.make("bpp.Wydawnictwo_Ciagle", rok=213)
    druga.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    res = client.get(reverse("bpp:browse_rok", args=(213,)), HTTP_HOST=site1.domain)
    assert res.status_code == 200
    assert reverse("bpp:browse_rok", args=(212,)) in res.content.decode()


@pytest.mark.django_db
def test_rok_spoza_zakresu_bez_danych_daje_404(client, site1, uczelnia1, settings):
    settings.ALLOWED_HOSTS = ["*"]
    res = client.get("/bpp/rok/777/", HTTP_HOST=site1.domain)
    assert res.status_code == 404


@pytest.mark.django_db
def test_rok_w_zakresie_bez_danych_daje_pusta_strone(
    client, site1, uczelnia1, settings
):
    """Zachowanie sprzed poprawki: rok z zakresu 1900-2100 bez rekordów to
    pusta lista (200), nie 404."""
    settings.ALLOWED_HOSTS = ["*"]
    res = client.get("/bpp/rok/2099/", HTTP_HOST=site1.domain)
    assert res.status_code == 200


@pytest.mark.django_db
def test_rok_poza_zakresem_integera_daje_404(client, site1, uczelnia1, settings):
    settings.ALLOWED_HOSTS = ["*"]
    res = client.get("/bpp/rok/99999999999999999999/", HTTP_HOST=site1.domain)
    assert res.status_code == 404
