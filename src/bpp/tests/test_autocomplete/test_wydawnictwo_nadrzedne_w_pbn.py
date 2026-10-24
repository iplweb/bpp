import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.system import odtworz_grupy
from bpp.views.autocomplete.wydawnictwo_nadrzedne_w_pbn import (
    Wydawnictwo_Nadrzedne_W_PBNAutocomplete,
)

URL_NAME = "bpp:wydawnictwo-nadrzedne-w-pbn-autocomplete"

LOCMEM_CACHES = {
    **settings.CACHES,
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-pbn-nadrzedne-rl",
    },
}


@pytest.fixture
def pbn_client_mock(mocker):
    """Podmienia ``Uczelnia.pbn_client`` — żadne zapytanie nie idzie do PBN."""
    client = mocker.MagicMock()
    client.search_publications.return_value = []
    mocker.patch("bpp.models.Uczelnia.pbn_client", return_value=client)
    return client


@pytest.fixture
def redaktor(django_user_model):
    odtworz_grupy()
    user = django_user_model.objects.create_user(username="redaktor", password="x")
    user.groups.add(Group.objects.get(name=GR_WPROWADZANIE_DANYCH))
    return user


@pytest.mark.django_db
def test_Wydawnictwo_Nadrzedne_W_PBNAutocomplete_post_mniej_jak_max_wiecej_jak_1(
    mocker, rf, pbn_uczelnia, admin_user
):
    x = Wydawnictwo_Nadrzedne_W_PBNAutocomplete()

    mocker.patch("pbn_integrator.utils.zapisz_mongodb")
    search_publications = mocker.patch("pbn_api.client.PBNClient.search_publications")
    mocker.patch("pbn_api.client.PBNClient.get_publication_by_id")

    search_publications.return_value = [
        {
            "mongoId": "asdf",
        }
    ] * 3  # mniej jak MAX, wiecej jak 1
    req = rf.post("/", {"text": "foobar"})
    req.user = admin_user

    x.request = req
    x.post(
        req,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("metoda", ["get", "post"])
def test_anonim_przekierowany_do_logowania(client, uczelnia, pbn_client_mock, metoda):
    url = reverse(URL_NAME)
    if metoda == "get":
        res = client.get(url, {"q": "foobar"})
    else:
        res = client.post(url, {"text": "foobar"})

    assert res.status_code == 302
    assert "login" in res["Location"]
    pbn_client_mock.search_publications.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("metoda", ["get", "post"])
def test_zalogowany_bez_grupy_403(
    client, uczelnia, pbn_client_mock, django_user_model, metoda
):
    user = django_user_model.objects.create_user(username="zwykly", password="x")
    client.force_login(user)
    url = reverse(URL_NAME)
    if metoda == "get":
        res = client.get(url, {"q": "foobar"})
    else:
        res = client.post(url, {"text": "foobar"})

    assert res.status_code == 403
    pbn_client_mock.search_publications.assert_not_called()


@pytest.mark.django_db
def test_grupa_bez_uprawnienia_dodawania_post_403(
    client, uczelnia, pbn_client_mock, django_user_model
):
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    grupa.permissions.clear()
    user = django_user_model.objects.create_user(username="bezperm", password="x")
    user.groups.add(grupa)
    client.force_login(user)

    res = client.post(reverse(URL_NAME), {"text": "foobar"})

    assert res.status_code == 403
    pbn_client_mock.search_publications.assert_not_called()


@pytest.mark.django_db
def test_redaktor_get_dziala(client, uczelnia, redaktor):
    client.force_login(redaktor)
    res = client.get(reverse(URL_NAME), {"q": "foobar"})

    assert res.status_code == 200
    assert "results" in res.json()


@pytest.mark.django_db
def test_redaktor_post_pyta_pbn(client, uczelnia, pbn_client_mock, redaktor):
    client.force_login(redaktor)
    res = client.post(reverse(URL_NAME), {"text": "foobar"})

    assert res.status_code == 200
    assert res.json()["text"] == "Nic (nowego) nie znaleziono w PBN."
    pbn_client_mock.search_publications.assert_called()


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHES)
def test_redaktor_post_throttling(
    client, uczelnia, pbn_client_mock, redaktor, monkeypatch
):
    cache.clear()
    monkeypatch.setattr(
        Wydawnictwo_Nadrzedne_W_PBNAutocomplete, "POST_RATELIMIT_MAX", 2
    )
    client.force_login(redaktor)
    url = reverse(URL_NAME)

    for _ in range(2):
        res = client.post(url, {"text": "foobar"})
        assert res.json()["text"] == "Nic (nowego) nie znaleziono w PBN."

    pbn_client_mock.search_publications.reset_mock()
    res = client.post(url, {"text": "foobar"})

    assert res.status_code == 200
    assert res.json()["id"] == "error"
    assert "Zbyt wiele" in res.json()["text"]
    pbn_client_mock.search_publications.assert_not_called()
    cache.clear()
